"""Tests for the Strands Agents provider."""

import asyncio
import copy
import json
from unittest.mock import MagicMock

import pydantic
import pytest
from composio_strands.provider import StrandsProvider
from strands.tools.registry import ToolRegistry
from strands.tools.tools import PythonAgentTool
from strands.types.tools import AgentTool

from composio.utils.shared import alias_tool_input_schema


def _tool(**overrides):
    base = {
        "slug": "GITHUB_GET_REPO",
        "name": "Github Get Repo",
        "description": "Get a repository",
        "input_parameters": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
            },
            "required": ["owner", "repo"],
        },
    }
    base.update(overrides)
    return MagicMock(**base)


def _invoke(agent_tool: AgentTool, tool_input, tool_use_id: str = "tu-1"):
    """Drive the tool through Strands' own ``stream`` path and return the result."""

    async def _collect():
        events = []
        async for event in agent_tool.stream(
            {
                "toolUseId": tool_use_id,
                "name": agent_tool.tool_name,
                "input": tool_input,
            },
            {},
        ):
            events.append(event)
        return events

    events = asyncio.run(_collect())
    assert len(events) == 1
    return events[-1]["tool_result"]


def test_wrap_tool_returns_strands_agent_tool_with_spec():
    tool = _tool()

    wrapped = StrandsProvider().wrap_tool(tool, lambda slug, arguments: {})

    assert isinstance(wrapped, AgentTool)
    assert isinstance(wrapped, PythonAgentTool)
    assert wrapped.tool_name == "GITHUB_GET_REPO"
    assert wrapped.tool_type == "python"
    assert wrapped.tool_spec == {
        "name": "GITHUB_GET_REPO",
        "description": "Get a repository",
        "inputSchema": {"json": tool.input_parameters},
    }


def test_wrap_tool_falls_back_to_generated_description():
    tool = _tool(description=None)

    wrapped = StrandsProvider().wrap_tool(tool, lambda slug, arguments: {})

    assert wrapped.tool_spec["description"] == "Execute GITHUB_GET_REPO"


def test_wrap_tool_does_not_mutate_input_parameters():
    tool = _tool(
        input_parameters={
            "type": "object",
            "properties": {"from": {"type": "string"}, "$top": {"type": "integer"}},
            "required": ["from"],
        }
    )
    snapshot = copy.deepcopy(tool.input_parameters)

    StrandsProvider().wrap_tool(tool, lambda slug, arguments: {})

    assert tool.input_parameters == snapshot


def test_execute_routes_through_execute_tool_and_returns_success():
    execute_tool = MagicMock(
        return_value={"successful": True, "data": {"stars": 42}, "error": None}
    )
    wrapped = StrandsProvider().wrap_tool(_tool(), execute_tool)

    result = _invoke(wrapped, {"owner": "composiohq", "repo": "composio"})

    execute_tool.assert_called_once_with(
        "GITHUB_GET_REPO", {"owner": "composiohq", "repo": "composio"}
    )
    assert result["toolUseId"] == "tu-1"
    assert result["status"] == "success"
    assert json.loads(result["content"][0]["text"]) == {
        "successful": True,
        "data": {"stars": 42},
        "error": None,
    }


def test_execute_restores_aliased_argument_names():
    """Keys that are not valid identifiers are aliased in the spec and restored on execute."""
    tool = _tool(
        input_parameters={
            "type": "object",
            "properties": {"from": {"type": "string"}, "$top": {"type": "integer"}},
            "required": ["from"],
        }
    )
    execute_tool = MagicMock(
        return_value={"successful": True, "data": {}, "error": None}
    )
    wrapped = StrandsProvider().wrap_tool(tool, execute_tool)

    # The spec must expose the same aliased names the core SDK produces, and
    # none of the original, invalid ones.
    expected = alias_tool_input_schema(tool.input_parameters)
    spec_properties = wrapped.tool_spec["inputSchema"]["json"]["properties"]
    assert spec_properties == expected.schema["properties"]
    assert "from" not in spec_properties
    assert "$top" not in spec_properties

    # Call with the aliased names the model would use; the backend must see the originals.
    alias_of = {original: alias for alias, original in expected.aliases.items()}
    _invoke(wrapped, {alias_of["from"]: "a", alias_of["$top"]: 5})

    execute_tool.assert_called_once_with("GITHUB_GET_REPO", {"from": "a", "$top": 5})


def test_execute_accepts_json_string_input():
    """Models sometimes emit tool input as a JSON string (issue #2406)."""
    execute_tool = MagicMock(
        return_value={"successful": True, "data": {}, "error": None}
    )
    wrapped = StrandsProvider().wrap_tool(_tool(), execute_tool)

    _invoke(wrapped, json.dumps({"owner": "o", "repo": "r"}))

    execute_tool.assert_called_once_with("GITHUB_GET_REPO", {"owner": "o", "repo": "r"})


def test_execute_maps_unsuccessful_response_to_error_status():
    execute_tool = MagicMock(
        return_value={"successful": False, "data": None, "error": "Not found"}
    )
    wrapped = StrandsProvider().wrap_tool(_tool(), execute_tool)

    result = _invoke(wrapped, {"owner": "o", "repo": "r"})

    assert result["status"] == "error"
    assert json.loads(result["content"][0]["text"])["error"] == "Not found"


def test_execute_reports_exceptions_as_error_results():
    execute_tool = MagicMock(side_effect=RuntimeError("backend down"))
    wrapped = StrandsProvider().wrap_tool(_tool(), execute_tool)

    result = _invoke(wrapped, {"owner": "o", "repo": "r"})

    assert result["status"] == "error"
    assert json.loads(result["content"][0]["text"]) == {
        "successful": False,
        "error": "backend down",
        "data": None,
    }


def test_execute_formats_pydantic_validation_errors():
    class Params(pydantic.BaseModel):
        owner: str

    def execute_tool(slug, arguments):
        Params()
        return {}

    wrapped = StrandsProvider().wrap_tool(_tool(), execute_tool)

    result = _invoke(wrapped, {"repo": "r"})

    assert result["status"] == "error"
    payload = json.loads(result["content"][0]["text"])
    assert payload["successful"] is False
    assert "owner" in payload["error"]


def test_wrap_tools_returns_list_of_agent_tools():
    tools = [_tool(slug="A_TOOL"), _tool(slug="B_TOOL")]

    wrapped = StrandsProvider().wrap_tools(tools, lambda slug, arguments: {})

    assert [w.tool_name for w in wrapped] == ["A_TOOL", "B_TOOL"]
    assert all(isinstance(w, AgentTool) for w in wrapped)


def test_wrapped_tools_register_in_strands_tool_registry():
    """The objects must be accepted by Strands' registry, which is what ``Agent(tools=...)`` uses."""
    wrapped = StrandsProvider().wrap_tools(
        [_tool(slug="GITHUB_GET_REPO"), _tool(slug="GMAIL_SEND_EMAIL")],
        lambda slug, arguments: {},
    )

    registry = ToolRegistry()
    registry.process_tools(wrapped)

    assert {"GITHUB_GET_REPO", "GMAIL_SEND_EMAIL"} <= set(registry.registry)
    # ``validate_tool_spec`` runs inside ``process_tools``; a spec Strands
    # rejects would have raised, so reaching the config map is the assertion.
    assert {"GITHUB_GET_REPO", "GMAIL_SEND_EMAIL"} <= set(
        registry.get_all_tools_config()
    )


@pytest.mark.parametrize("tool_input", [None, "", "   "])
def test_execute_treats_missing_input_as_empty_arguments(tool_input):
    execute_tool = MagicMock(
        return_value={"successful": True, "data": {}, "error": None}
    )
    wrapped = StrandsProvider().wrap_tool(
        _tool(
            slug="NO_ARG_TOOL", input_parameters={"type": "object", "properties": {}}
        ),
        execute_tool,
    )

    _invoke(wrapped, tool_input)

    execute_tool.assert_called_once_with("NO_ARG_TOOL", {})

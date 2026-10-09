"""
Strands Agents provider for Composio.

Wraps Composio tools as Strands ``AgentTool`` instances so they can be passed
straight to ``strands.Agent(tools=...)``. Execution goes through Composio's
``execute_tool`` callback, so direct execution (``composio.tools.get``) and
Tool Router sessions (``session.tools()``) both work unchanged.
"""

from __future__ import annotations

import json
import typing as t

import pydantic
from strands.tools.tools import PythonAgentTool
from strands.types.tools import AgentTool, ToolResult, ToolSpec, ToolUse

from composio.core.provider import AgenticProvider
from composio.core.provider.agentic import AgenticProviderExecuteFn
from composio.types import Tool
from composio.utils.pydantic import parse_pydantic_error
from composio.utils.shared import alias_tool_input_schema, normalize_tool_arguments


def _tool_result(tool_use_id: str, status: str, payload: t.Any) -> ToolResult:
    """Build a Strands ``ToolResult`` carrying ``payload`` as a JSON text block.

    Text is used rather than the ``json`` content type because every Strands
    model provider accepts text, while ``json`` blocks are only guaranteed on
    the Bedrock Converse path.
    """
    return t.cast(
        ToolResult,
        {
            "toolUseId": tool_use_id,
            "status": status,
            "content": [{"text": json.dumps(payload, default=str)}],
        },
    )


def _error_result(tool_use_id: str, error: str) -> ToolResult:
    return _tool_result(
        tool_use_id,
        "error",
        {"successful": False, "error": error, "data": None},
    )


class StrandsProvider(
    AgenticProvider[AgentTool, list[AgentTool]],
    name="strands",
):
    """
    Composio provider for the Strands Agents SDK.

    Each Composio tool becomes a ``strands.tools.tools.PythonAgentTool`` whose
    ``tool_spec`` carries the tool's slug, description and (aliased) JSON
    schema, and whose callable executes the tool through Composio. The wrapped
    tools are ordinary ``AgentTool`` objects, so they can be mixed with
    ``@tool``-decorated functions, MCP tools and ``strands_tools``.

    Example:
        ```python
        from strands import Agent

        from composio import Composio
        from composio_strands import StrandsProvider

        composio = Composio(provider=StrandsProvider())
        tools = composio.tools.get(user_id="default", toolkits=["github"])

        agent = Agent(tools=tools)
        agent("Star the composiohq/composio repository")
        ```
    """

    def wrap_tool(
        self,
        tool: Tool,
        execute_tool: AgenticProviderExecuteFn,
    ) -> AgentTool:
        """Wrap a Composio tool as a Strands ``AgentTool``."""
        slug = tool.slug
        # Aliasing makes the provider-facing schema safe for the Anthropic-style
        # validators that Strands model providers apply, and gives us the
        # reverse map needed to restore the original argument names before the
        # call reaches the Composio backend. It deep-copies, so the caller's
        # ``Tool.input_parameters`` is never mutated.
        aliases = alias_tool_input_schema(tool.input_parameters or {})

        tool_spec: ToolSpec = {
            "name": slug,
            "description": tool.description or f"Execute {slug}",
            "inputSchema": {"json": aliases.schema},
        }

        def run(tool_use: ToolUse, **_: t.Any) -> ToolResult:
            """Execute the Composio tool for a Strands ``ToolUse`` request.

            Strands runs synchronous tool callables in a worker thread, so the
            blocking ``execute_tool`` call does not stall the agent event loop.
            """
            tool_use_id = tool_use["toolUseId"]
            try:
                # Models occasionally emit tool input as a JSON string rather
                # than a dict (issue #2406); normalize before restoring aliases.
                arguments = aliases.restore_arguments(
                    normalize_tool_arguments(tool_use.get("input"))
                )
                result = execute_tool(slug, arguments)
            except pydantic.ValidationError as e:
                return _error_result(tool_use_id, parse_pydantic_error(e))
            except Exception as e:  # noqa: BLE001 - surface any failure to the model
                return _error_result(tool_use_id, str(e))

            successful = (
                result.get("successful", True) if isinstance(result, dict) else True
            )
            return _tool_result(
                tool_use_id, "success" if successful else "error", result
            )

        # ``ToolFunc`` expects a ``__name__``; use the slug so tracebacks and
        # telemetry identify the tool rather than the wrapper.
        run.__name__ = slug
        return PythonAgentTool(tool_name=slug, tool_spec=tool_spec, tool_func=run)

    def wrap_tools(
        self,
        tools: t.Sequence[Tool],
        execute_tool: AgenticProviderExecuteFn,
    ) -> list[AgentTool]:
        """Wrap a sequence of Composio tools as Strands ``AgentTool`` objects."""
        return [self.wrap_tool(tool, execute_tool) for tool in tools]

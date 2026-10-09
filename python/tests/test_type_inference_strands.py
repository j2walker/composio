"""
Type inference verification tests for Strands Agents provider.

This file verifies that type checkers correctly infer `list[AgentTool]`
when using the Strands provider with Composio.

**This file is NOT executed at runtime.** It is analyzed statically by type
checkers to verify that type inference works correctly.

Run: mypy tests/test_type_inference_strands.py

Requirements:
    - composio (core SDK)
    - composio-strands
    - strands-agents
"""

from typing import TYPE_CHECKING

from composio import Composio

if TYPE_CHECKING:
    from composio_strands import StrandsProvider
    from strands.types.tools import AgentTool
    from typing_extensions import assert_type


def test_strands_provider_toolkits() -> None:
    """Verify Strands provider returns list[AgentTool] for toolkits query."""
    if TYPE_CHECKING:
        composio: Composio[AgentTool, list[AgentTool]] = Composio(
            provider=StrandsProvider()
        )
        tools = composio.tools.get(user_id="test", toolkits=["github"])

        # Type checker should infer: list[AgentTool]
        assert_type(tools, list[AgentTool])


def test_strands_provider_slug() -> None:
    """Verify Strands provider returns list[AgentTool] for slug query."""
    if TYPE_CHECKING:
        composio: Composio[AgentTool, list[AgentTool]] = Composio(
            provider=StrandsProvider()
        )
        tools = composio.tools.get(user_id="test", slug="GITHUB_CREATE_REPO")

        assert_type(tools, list[AgentTool])


def test_strands_provider_tools_list() -> None:
    """Verify Strands provider returns list[AgentTool] for tools list query."""
    if TYPE_CHECKING:
        composio: Composio[AgentTool, list[AgentTool]] = Composio(
            provider=StrandsProvider()
        )
        tools = composio.tools.get(
            user_id="test",
            tools=["GITHUB_CREATE_REPO", "GITHUB_GET_USER"],
        )

        assert_type(tools, list[AgentTool])


def test_strands_provider_search() -> None:
    """Verify Strands provider returns list[AgentTool] for search query."""
    if TYPE_CHECKING:
        composio: Composio[AgentTool, list[AgentTool]] = Composio(
            provider=StrandsProvider()
        )
        tools = composio.tools.get(user_id="test", search="github repository")

        assert_type(tools, list[AgentTool])


def test_strands_provider_inferred() -> None:
    """Verify Strands provider type is correctly inferred without explicit annotation."""
    if TYPE_CHECKING:
        composio = Composio(provider=StrandsProvider())
        tools = composio.tools.get(user_id="test", toolkits=["github"])

        # Should infer list[AgentTool] from provider type
        assert_type(tools, list[AgentTool])

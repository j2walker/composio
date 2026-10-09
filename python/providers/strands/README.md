# composio-strands

Adapts Composio tools to the [Strands Agents SDK](https://strandsagents.com), exposing each Composio tool as a native Strands `AgentTool` that can be passed straight to `strands.Agent(tools=...)`.

## Installation

```bash
pip install composio composio-strands strands-agents
```

Set `COMPOSIO_API_KEY` (from the [dashboard](https://dashboard.composio.dev/settings)) in your environment, plus the credentials for whichever model provider you use with Strands (Bedrock by default; Anthropic, OpenAI, Gemini and others via the `strands-agents[...]` extras).

## Quickstart

```python
from strands import Agent

from composio import Composio
from composio_strands import StrandsProvider

composio = Composio(provider=StrandsProvider())

# Each session is scoped to one of your users
session = composio.create(user_id="user_123")
tools = session.tools()

agent = Agent(
    system_prompt="You are a helpful assistant. Use Composio tools to take action.",
    tools=tools,
)

agent("Summarize my emails from today")
```

For multi-turn use, store `session.session_id` and reuse it with `composio.use(session_id)` instead of calling `create()` again.

## Direct tool execution

If you want a fixed tool set instead of a Tool Router session, fetch tools by toolkit or slug:

```python
tools = composio.tools.get(user_id="user_123", toolkits=["github"])
agent = Agent(tools=tools)
agent("Star the composiohq/composio repository")
```

## How tools are exposed

`session.tools()` and `composio.tools.get()` return `strands.tools.tools.PythonAgentTool` objects:

- `tool_spec` carries the Composio slug as the tool name, the tool description, and the input JSON schema under `inputSchema.json`, which is the shape every Strands model provider consumes.
- Schema property names that are not valid identifiers (for example `from` or `$top`) are aliased in the spec and restored before the call reaches Composio, matching the other Python providers.
- Execution runs through Composio's `execute_tool` callback inside Strands' worker thread, so the blocking HTTP call does not stall the agent loop. Results are returned as a JSON text block with Composio's `{"successful", "data", "error"}` shape; a failed execution is reported with `status: "error"` so the model can recover.

Because the wrapped tools are ordinary `AgentTool` objects, they can be mixed freely with `@tool`-decorated functions, `strands_tools`, and MCP tools in the same agent.

## Links

- [Quickstart](https://docs.composio.dev/docs/quickstart)
- [Composio documentation](https://docs.composio.dev)
- [Strands Agents documentation](https://strandsagents.com/latest/)

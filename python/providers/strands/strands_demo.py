"""
Strands Agents demo.

Requires COMPOSIO_API_KEY plus model credentials for Strands (AWS credentials
for the default Bedrock model, or pass an explicit model such as
``strands.models.anthropic.AnthropicModel``).
"""

from composio_strands import StrandsProvider
from strands import Agent

from composio import Composio

# Initialize Composio with the Strands provider
composio = Composio(provider=StrandsProvider())

# Fetch a Composio tool as a Strands AgentTool
tools = composio.tools.get(
    user_id="default",
    tools=["GITHUB_STAR_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER"],
)

agent = Agent(
    system_prompt="You are a helpful assistant that helps users with GitHub tasks.",
    tools=tools,
)

result = agent(
    "Star the repository composiohq/composio on GitHub. If done "
    "successfully, respond with 'Action executed successfully'"
)
print(result)

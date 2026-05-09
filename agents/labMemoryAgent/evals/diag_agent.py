"""Diagnose the agent's current state."""
import os
from pathlib import Path
from azure.ai.agents import AgentsClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")
c = AgentsClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)
agent = c.get_agent("asst_I9vO5sAp69FmXwylop75vP2c")
print(f"name={agent.name}")
print(f"model={agent.model}")
print(f"temperature={getattr(agent, 'temperature', '?')}")
print(f"tools={[t.type for t in agent.tools]}")

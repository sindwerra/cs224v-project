import asyncio
import json
import os
import sys

# Ensure project root is on sys.path so `agent_sdk` can be imported
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agents import Agent, Tool, Runner, function_tool, SQLiteSession
from agent_sdk.hf_agents_sdk import build_hf_agent

async def run_conv():
    print("You are now chatting with Heart-Failure Titration Agent, Type 'exit' to end the conversation.")
    session = SQLiteSession("Conv_123")
    agent = build_hf_agent()

    import json as _json

    while True:
        user_input = input("You: ")
        print("You: " + user_input)
        
        if user_input == "exit":
            print("Goodbye!")
            break
        result = await Runner.run(agent, user_input, session=session)
        print(f"Agent: {result.final_output}")


if __name__ == "__main__":
    asyncio.run(run_conv())
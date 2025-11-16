import asyncio
import json
import os
import sys

# Ensure project root is on sys.path so `agent_sdk` can be imported
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agents import Agent, Tool, Runner, function_tool, SQLiteSession
from agent_sdk.hf_agents_sdk import build_hf_agent, AgentContext


async def run_conv():
    print(
        """
        Welcome! I'm here to assist you with your heart failure medication plan. 
        As your virtual assistant, please feel free to share your questions 
        or updates about how you're feeling, and we can work through them together. 
        If you need to end our conversation at any time, just let me know by 
        saying "exit."
        """
    )
    session = SQLiteSession("Conv_123")
    agent = build_hf_agent()

    agent_context = AgentContext()

    while True:
        user_input = input("You: ")
        # print("You: " + user_input)
        
        if user_input == "exit":
            print("Goodbye!")
            break
        result = await Runner.run(
            agent,
            user_input,
            session=session,
            context=agent_context,
        )
        print(f"Agent: {result.final_output}")


if __name__ == "__main__":
    asyncio.run(run_conv())
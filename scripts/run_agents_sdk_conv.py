import asyncio
import json
import os
import sys

# Ensure project root is on sys.path so `agent_sdk` can be imported
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agents import Agent, Tool, Runner, function_tool, SQLiteSession
from agent_sdk.hf_agents_sdk import build_hf_agent, AgentContext, get_db


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
        db = get_db()
        if db and agent_context.patient_doc:
            try:
                db.create_message(
                    user_id=agent_context.patient_doc.patient_id,
                    user_text=user_input,
                    assistant_text=result.final_output or "",
                    model=agent.model,
                )
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(run_conv())
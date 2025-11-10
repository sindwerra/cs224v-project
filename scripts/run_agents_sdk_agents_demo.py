import asyncio
import json
import os
import sys

# Ensure project root is on sys.path so `agent_sdk` can be imported
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent_sdk.hf_agents_sdk import run_once


async def main():
    # Example: normal case
    normal_fields = {
        "vitals_sbp": 110,
        "vitals_dbp": 70,
        "vitals_hr": 64,
        "labs_creatinine_mg_dl": 1.2,
        "labs_egfr": 55,
        "labs_potassium_mmol_l": 4.6,
        "symptoms": [],
        "meds": [],
    }
    r1 = await run_once("Here are my latest vitals and labs.", normal_fields)
    print("=== NORMAL ===")
    print(json.dumps(r1, indent=2, default=str))

    # Example: high-risk case (SBP<80)
    risk_fields = dict(normal_fields)
    risk_fields["vitals_sbp"] = 75
    risk_fields["symptoms"] = ["dizziness"]
    r2 = await run_once("I feel dizzy. These are my readings.", risk_fields)
    print("\n=== HIGH RISK ===")
    print(json.dumps(r2, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())



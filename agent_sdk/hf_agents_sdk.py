"""
HF-Agent implemented with OpenAI Agents SDK.
Layers:
- risk_evaluator_tool: SDK Tool wrapping our red-flag evaluator
- build_hf_agent: returns an Agent with instructions + tool
- save_episode_stub / append_message_stub: MongoDB placeholders (no I/O)

Docs reference:
- OpenAI Agents SDK Quickstart: https://openai.github.io/openai-agents-python/quickstart/
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel

# SDK imports (soft dependency)
try:
    from agents import Agent, Tool, Runner, function_tool, SQLiteSession  # type: ignore
    HAS_AGENTS_SDK = True
except Exception:
    HAS_AGENTS_SDK = False
    Agent = object  # type: ignore
    Tool = object  # type: ignore
    Runner = object  # type: ignore

from .red_flags import evaluate_red_flags, to_structured_state


def save_episode_stub(payload: Dict[str, Any]) -> None:
    _ = payload
    return


def append_message_stub(episode_id: str, message: Dict[str, Any]) -> None:
    _ = (episode_id, message)
    return


class MedItem(BaseModel):
    name: str
    dose: Optional[str] = None


class RiskResult(BaseModel):
    risk_level: Literal["high", "moderate", "none"]
    flags: List[str]


@function_tool(name_override="risk_evaluator_tool")
def risk_evaluator_tool(
    vitals_sbp: Optional[float] = None,
    vitals_dbp: Optional[float] = None,
    vitals_hr: Optional[float] = None,
    labs_creatinine_mg_dl: Optional[float] = None,
    labs_egfr: Optional[float] = None,
    labs_potassium_mmol_l: Optional[float] = None,
    symptoms: Optional[List[str]] = None,
    meds: Optional[List[MedItem]] = None,
) -> RiskResult:
    """
    Strictly typed function tool to satisfy Agents SDK strict JSON schema.
    """
    ps = to_structured_state(
        vitals_sbp=vitals_sbp,
        vitals_dbp=vitals_dbp,
        vitals_hr=vitals_hr,
        labs_creatinine_mg_dl=labs_creatinine_mg_dl,
        labs_egfr=labs_egfr,
        labs_potassium_mmol_l=labs_potassium_mmol_l,
        symptoms=symptoms or [],
        meds=[m.model_dump() for m in (meds or [])],
    )
    flags, level = evaluate_red_flags(ps)
    return RiskResult(risk_level=level, flags=flags)


def build_hf_agent() -> Agent:
    """
    Create a single agent with one tool for risk evaluation.
    """
    if not HAS_AGENTS_SDK:
        raise RuntimeError(
            "openai-agents not installed. Install with `pip install openai-agents` "
            "and follow the Quickstart: https://openai.github.io/openai-agents-python/quickstart/"
        )

    agent = Agent(
        name="HF-Intake-Agent",
        instructions=(
            "You are a heart failure medication assistant. "
            "Collect vitals/labs/symptoms/meds. "
            # "When the key fields are present, use the tool risk_evaluator_tool to screen for red-flags "
            # "(e.g., SBP<80, SBP<90 with symptoms, K+>=6.0, eGFR<20, HR<50). "
            # "If high-risk, warn and stop titration; otherwise, confirm that the case will be sent to the physician."
        ),
        tools=[risk_evaluator_tool],
    )
    return agent


async def run_once(input_text: str, flat_fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestrate one run: the input_text is the user message, flat_fields carries the numeric inputs
    to pass to the tool call (the agent can ask to call the tool).
    We simulate the tool call by providing a context item 'flat_fields' to the Runner.
    """
    if not HAS_AGENTS_SDK:
        raise RuntimeError(
            "openai-agents not installed. Install with `pip install openai-agents` "
            "and follow the Quickstart: https://openai.github.io/openai-agents-python/quickstart/"
        )

    agent = build_hf_agent()

    # In a simple pattern, the agent can produce a tool call; we expose args via context.
    # Some SDK usages pass context via Runner; here we place everything into input for simplicity.
    # The agent's tool function will be called with args deduced from the conversation (or directly provided).
    # Hint the agent to call the tool with the given structured fields
    import json as _json
    hint = (
        input_text
        + "\nUse the following structured fields when calling risk_evaluator_tool: "
        + _json.dumps(flat_fields)
    )
    result = await Runner.run(agent, hint)
    # result.final_output may be a string; tools' returns show up in trace. We return both.
    return {
        "final_output": getattr(result, "final_output", None),
        "result": getattr(result, "result", None),
    }

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
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid

# SDK imports (soft dependency)
try:
    from agents import Agent, Tool, Runner, function_tool, SQLiteSession, RunContextWrapper, handoff  # type: ignore
    # Handoff prompt prefix for main agent orchestration
    from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX  # type: ignore
    HAS_AGENTS_SDK = True
except Exception:
    HAS_AGENTS_SDK = False
    Agent = object  # type: ignore
    Tool = object  # type: ignore
    Runner = object  # type: ignore

from .red_flags import evaluate_red_flags, to_structured_state

 # (stubs potentially overridden by mongo_store above)


class MedItem(BaseModel):
    name: str
    dose: Optional[str] = None


class RiskResult(BaseModel):
    risk_level: Literal["high", "moderate", "none"]
    flags: List[str]


# ---------------------------------------------------------------------------
# Receptionist tool: establish patient context (fake DB read/write).
# The schema follows the Patients collection shape in db layer.
# ---------------------------------------------------------------------------
class PatientDemographics(BaseModel):
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None


class PatientDoc(BaseModel):
    patient_id: str
    demographics: PatientDemographics
    created_at: str
    updated_at: str
    latest_patient_state: Optional[Dict[str, Any]] = None


class HandoffInfo(BaseModel):
    subagent_name: str = Field(description="The name of the subagent being called.")
    reason: str = Field(description="The reason for the handoff.")


@dataclass
class AgentContext:
    patient_doc: Optional[PatientDoc] = None


@function_tool(name_override="patient_context_tool")
def patient_context_tool(
    wrapper: RunContextWrapper[AgentContext],
    name: Optional[str] = None,
    patient_id: Optional[str] = None,
) -> PatientDoc:
    """
    Load or create a patient document (fake DB).
    - If patient_id provided and recognized, return an existing record with a recent patient_state snapshot.
    - Else, create a new patient with a generated patient_id and basic demographics from 'name'.
    The returned structure follows the Patients collection style used in our db module.
    """
    print(f"patient_context_tool被调用: patient_id={patient_id}, name={name}")
    now = datetime.now(timezone.utc).isoformat()

    # 模拟一个现有患者分支
    if patient_id == "P_EXISTING_001":
        patient_doc = PatientDoc(
            patient_id="P_EXISTING_001",
            demographics=PatientDemographics(name=name or "Existing Patient", age=68, gender="M"),
            created_at=now,
            updated_at=now,
            latest_patient_state={
                "vitals": {"sbp": 112, "dbp": 72, "hr": 66, "weight_kg": 78.0},
                "labs": {"creatinine_mg_dl": 1.1, "egfr": 58, "potassium_mmol_l": 4.4},
                "symptoms": [],
                "meds": [{"name": "sacubitril/valsartan", "dose": "49/51mg bid"}],
            },
        )
    # 否则“创建”一个新患者
    else:
        new_id = f"P_{uuid.uuid4().hex[:8].upper()}"
        print(new_id)
        patient_doc = PatientDoc(
            patient_id=new_id,
            demographics=PatientDemographics(name=name or "New Patient"),
            created_at=now,
            updated_at=now,
            latest_patient_state=None,
        )

    # 将生成的 patient_doc 存储在上下文中
    print(patient_doc)
    wrapper.context.patient_doc = patient_doc
    print(f"在 patient_context_tool 中更新上下文: patient_doc.patient_id={wrapper.context.patient_doc.patient_id}")
    return patient_doc


@function_tool(name_override="risk_evaluator_tool")
def risk_evaluator_tool(
    wrapper: RunContextWrapper[AgentContext],
    # vitals_sbp: Optional[float] = None,
    # vitals_dbp: Optional[float] = None,
    # vitals_hr: Optional[float] = None,
    vitals_sbp: float,
    vitals_dbp: float,
    vitals_hr: float,
    labs_creatinine_mg_dl: Optional[float] = None,
    labs_egfr: Optional[float] = None,
    labs_potassium_mmol_l: Optional[float] = None,
    symptoms: Optional[List[str]] = None,
    meds: Optional[List[MedItem]] = None,
) -> RiskResult:
    """
    Strictly typed function tool to satisfy Agents SDK strict JSON schema.
    """
    patient_doc = wrapper.context.patient_doc
    if patient_doc:
        print(f"risk_evaluator_tool 正在处理患者: patient_id={patient_doc.patient_id}, name={patient_doc.demographics.name}")
    else:
        print("risk_evaluator_tool 在上下文中未找到患者文档。")
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


async def on_handoff(ctx: RunContextWrapper[None], input_data: HandoffInfo):
    print(f"Handoff 到 '{input_data.subagent_name}' 因为 '{input_data.reason}'")
    
    # 在这里可以访问上下文中的 patient_doc
    if ctx.context and ctx.context.patient_doc:
        print(f"Handoff 时发现 patient_id: {ctx.context.patient_doc.patient_id}")
    else:
        print("Handoff 时上下文中没有 patient_doc")


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
        name="hf_intake_agent",
        instructions=(
            "You are a heart failure medication assistant. "
            "Collect vitals/labs/symptoms/meds. "
            "When the key fields are present, use the tool risk_evaluator_tool to screen for red-flags "
            "(e.g., SBP<80, SBP<90 with symptoms, K+>=6.0, eGFR<20, HR<50). "
            "If high-risk, warn and stop titration; otherwise, confirm that the case will be sent to the physician."
        ),
        tools=[risk_evaluator_tool],
    )

    intake_handoff = handoff(
        agent=agent,
        # on_handoff=on_handoff,
        # input_type=HandoffInfo,
    )

    # Main Agent (receptionist/orchestrator with handoff to HF-Intake-Agent)
    # Behavior:
    # 1) First call patient_context_tool to either load an existing patient (by patient_id)
    #    or create a new patient (by name). Keep the conversation short and confirm context.
    # 2) After patient context is established, handoff to HF-Intake-Agent for clinical intake/risk screen.
    # 3) Do not expose internal orchestration details to the user.
    receptionist_instructions = (
        RECOMMENDED_PROMPT_PREFIX
        + "\nYou are the receptionist agent for a heart failure medication service. "
        "For each conversation:\n"
        "- If patient_id is provided, call patient_context_tool to load context; otherwise collect the patient's name and call patient_context_tool to create a record.\n"
        "- Briefly acknowledge the context (without dumping all fields) and then handoff to HF-Intake-Agent to continue clinical assessment and risk screening.\n"
        "- Keep your messages concise and friendly. Do not reveal internal handoff details."
    )

    main_agent = Agent(
        name="Main Agent",
        instructions=receptionist_instructions,
        handoffs=[intake_handoff],  # allow handoff to the clinical intake agent
        handoff_description=(
            "Use the HF-Intake-Agent after the patient context has been loaded/created "
            "to collect required vitals/labs/symptoms/meds and perform red-flag screening."
        ),
        tools=[patient_context_tool],
    )

    return main_agent


# async def run_once(input_text: str, flat_fields: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Orchestrate one run: the input_text is the user message, flat_fields carries the numeric inputs
#     to pass to the tool call (the agent can ask to call the tool).
#     We simulate the tool call by providing a context item 'flat_fields' to the Runner.
#     """
#     if not HAS_AGENTS_SDK:
#         raise RuntimeError(
#             "openai-agents not installed. Install with `pip install openai-agents` "
#             "and follow the Quickstart: https://openai.github.io/openai-agents-python/quickstart/"
#         )

#     agent = build_hf_agent()

#     # In a simple pattern, the agent can produce a tool call; we expose args via context.
#     # Some SDK usages pass context via Runner; here we place everything into input for simplicity.
#     # The agent's tool function will be called with args deduced from the conversation (or directly provided).
#     # Hint the agent to call the tool with the given structured fields
#     import json as _json
#     hint = (
#         input_text
#         + "\nUse the following structured fields when calling risk_evaluator_tool: "
#         + _json.dumps(flat_fields)
#     )
#     result = await Runner.run(agent, hint)
#     # result.final_output may be a string; tools' returns show up in trace. We return both.
#     return {
#         "final_output": getattr(result, "final_output", None),
#         "result": getattr(result, "result", None),
#     }

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
from dotenv import load_dotenv
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import json
import os
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
from database import HFAgentDatabase, generate_user_id
try:
    import openai  # type: ignore
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


_db_instance: Optional[HFAgentDatabase] = None


def get_db() -> Optional[HFAgentDatabase]:
    global _db_instance
    if _db_instance is not None:
        return _db_instance
    if HFAgentDatabase is None:
        return None
    load_dotenv()
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    print(mongodb_uri)
    _db_instance = HFAgentDatabase(mongodb_uri)
    return _db_instance


def _normalize_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


def _normalize_state(raw: Dict[str, Any]) -> Dict[str, Any]:
    vitals = raw.get("vitals") or {}
    labs = raw.get("labs") or {}
    return {
        "vitals": {
            "sbp": _normalize_number(vitals.get("sbp")),
            "dbp": _normalize_number(vitals.get("dbp")),
            "hr": _normalize_number(vitals.get("hr")),
        },
        "labs": {
            "creatinine_mg_dl": _normalize_number(labs.get("creatinine_mg_dl")),
            "egfr": _normalize_number(labs.get("egfr")),
            "potassium_mmol_l": _normalize_number(labs.get("potassium_mmol_l")),
        },
        "symptoms": raw.get("symptoms") or [],
        "meds": raw.get("meds") or [],
        # "adherence": raw.get("adherence"),
    }


def _build_messages_payload(messages: List[Dict[str, Any]]) -> str:
    payload_lines = []
    for msg in messages[:20]:
        role = "user" if msg.get("user", {}).get("text") else "assistant"
        text = msg.get(role, {}).get("text", "")
        ts = msg.get(role, {}).get("ts", "")
        payload_lines.append(f"{role.title()} ({ts}): {text}")
    return "\n".join(payload_lines)


def extract_patient_state_from_messages(messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not messages:
        return None
    ordered = sorted(messages, key=lambda m: m.get("created_at", datetime.min), reverse=True)
    payload = _build_messages_payload(ordered)
    if not payload:
        return None

    load_dotenv()
    if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
        system_prompt = (
            "You are a concise clinical summarizer. "
            "Given a conversation transcript (most recent first), output only JSON with keys "
            "`vitals`, `labs`, `symptoms`, `meds`, `adherence`. "
            "Each key should map to the latest reported value. Example:\n"
            '{"vitals":{"sbp":110,"dbp":70,"hr":64},"labs":{"creatinine_mg_dl":1.2,"egfr":55,"potassium_mmol_l":4.5},"symptoms":["fatigue"],"meds":[{"name":"lisinopril","dose":"20mg"}],"adherence":"good"}'
        )
        user_prompt = f"Conversation:\n{payload}\nReturn the JSON described above."
        try:
            response = openai.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
            )
            content = response.choices[0].message.content
            parsed = json.loads(content.strip())
            return _normalize_state(parsed)
        except Exception as e:
            print(e)
    return None

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
    is_existing_patient: bool,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    patient_id: Optional[str] = None,
) -> PatientDoc:
    """
    Load or create a patient document.
    
    Parameters:
    - is_existing_patient: REQUIRED. True if patient has used this service before, False if new patient.
    - patient_id: For existing patients, their patient ID (if known)
    - email: Email address (for existing patient lookup OR new patient creation)
    - phone: Phone number (for existing patient lookup OR new patient creation)
    - name: Full name (required for new patients, optional for existing)
    
    For existing patients (is_existing_patient=True):
    - At least ONE of: patient_id, email, or phone must be provided
    - Search by patient_id, email, or phone (in that priority order)
    - Return existing record with latest_patient_state snapshot from message history
    - If not found, raise error indicating patient not found
    
    For new patients (is_existing_patient=False):
    - Require all three fields: name, email, and phone
    - Create new patient record with generated patient_id
    - Return new PatientDoc with empty latest_patient_state
    
    Returns PatientDoc following the Patients collection schema.
    """
    print(f"patient_context_tool被调用: is_existing_patient={is_existing_patient}, patient_id={patient_id}, name={name}, email={email}, phone={phone}")
    now = datetime.now(timezone.utc).isoformat()

    db = get_db()
    patient_doc: Optional[PatientDoc] = None
    existing_user = None

    # ========== EXISTING PATIENT FLOW ==========
    if is_existing_patient:
        # Must provide at least one identifier
        if not patient_id and not email and not phone:
            error_msg = "对于已存在的患者,必须提供至少一个识别信息: patient_id, email 或 phone"
            print(error_msg)
            raise ValueError(error_msg)
        
        # Try to find existing patient by patient_id, email, or phone
        if db:
            if patient_id:
                existing_user = db.get_user(patient_id)
                print(f"通过patient_id查找: {'找到' if existing_user else '未找到'}")
            
            if not existing_user and email:
                existing_user = db.get_user_by_email(email)
                print(f"通过email查找: {'找到' if existing_user else '未找到'}")
            
            if not existing_user and phone:
                existing_user = db.get_user_by_phone(phone)
                print(f"通过phone查找: {'找到' if existing_user else '未找到'}")

        # If found existing user, load their context
        if existing_user:
            messages = db.get_messages_by_user(
                existing_user["_id"], message_type="conversation") if db else []
            latest_state = extract_patient_state_from_messages(messages)
            patient_doc = PatientDoc(
                patient_id=existing_user["_id"],
                demographics=PatientDemographics(
                    name=existing_user["profile"]["name"],
                    age=existing_user["profile"].get("age"),
                    gender=existing_user["profile"].get("sex"),
                ),
                created_at=str(existing_user.get("created_at", now)),
                updated_at=now,
                latest_patient_state=latest_state,
            )
            print(f"✓ 加载已存在患者: {patient_doc.patient_id}, 姓名: {patient_doc.demographics.name}")
        else:
            # Patient claims to be existing but not found in database
            identifiers = []
            if patient_id:
                identifiers.append(f"patient_id={patient_id}")
            if email:
                identifiers.append(f"email={email}")
            if phone:
                identifiers.append(f"phone={phone}")
            error_msg = f"未找到匹配的患者记录。提供的信息: {', '.join(identifiers)}"
            print(error_msg)
            raise ValueError(error_msg)
    
    # ========== NEW PATIENT FLOW ==========
    else:
        # For new patients, require all three mandatory fields
        if not name or not email or not phone:
            missing = []
            if not name:
                missing.append("name")
            if not email:
                missing.append("email")
            if not phone:
                missing.append("phone")
            error_msg = f"创建新患者需要提供所有必填字段。缺少: {', '.join(missing)}"
            print(error_msg)
            raise ValueError(error_msg)
        
        # Check if patient already exists (to avoid duplicates)
        if db:
            existing_check = db.get_user_by_email(email)
            if not existing_check:
                existing_check = db.get_user_by_phone(phone)
            
            if existing_check:
                error_msg = f"该邮箱或电话号码已被注册。患者ID: {existing_check['_id']}, 姓名: {existing_check['profile']['name']}"
                print(error_msg)
                raise ValueError(error_msg)
        
        # Create new patient
        new_id = generate_user_id()
        profile = {"name": name, "dob": "", "sex": ""}
        contact = {"phone": phone, "email": email}
        
        patient_doc = PatientDoc(
            patient_id=new_id,
            demographics=PatientDemographics(name=name),
            created_at=now,
            updated_at=now,
            latest_patient_state=None,
        )
        
        if db:
            try:
                db.create_user(
                    user_id=new_id,
                    role="patient",
                    profile=profile,
                    contact=contact,
                )
                print(f"✓ 成功创建新患者: {new_id}, 姓名: {name}, 邮箱: {email}, 电话: {phone}")
            except Exception as e:
                print(f"✗ 创建患者时出错: {e}")
                raise

    # Store patient_doc in context
    wrapper.context.patient_doc = patient_doc
    print(f"在 patient_context_tool 中更新上下文: patient_doc.patient_id={wrapper.context.patient_doc.patient_id}")
    return patient_doc


@function_tool(name_override="risk_evaluator_tool")
def risk_evaluator_tool(
    wrapper: RunContextWrapper[AgentContext],
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


class RecommendationResult(BaseModel):
    action: Literal["titrate", "maintain", "hold", "escalate"]
    recommendation_text: str
    new_medications: Optional[List[MedItem]] = None
    rationale: str


def _load_titration_protocol() -> str:
    """Load the Heart Failure Medication Titration Protocol document"""
    protocol_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "knowledge_base",
        "Heart Failure Medication Titration Protocol.md"
    )
    try:
        with open(protocol_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Warning: Could not load protocol document: {e}")
        return ""


def _generate_llm_recommendation(
    patient_state: Dict[str, Any],
    risk_level: str,
    protocol_text: str
) -> Dict[str, Any]:
    """
    Use LLM to generate recommendation based on protocol document
    
    Returns dict with:
        - action: str
        - recommendation_text: str
        - rationale: str
        - requires_manual_review: bool
    """
    if not OPENAI_AVAILABLE or not os.getenv("OPENAI_API_KEY"):
        return {
            "action": "hold",
            "recommendation_text": "Unable to generate recommendation: OpenAI API not available",
            "rationale": "API configuration missing",
            "requires_manual_review": True
        }
    
    # Build patient summary
    vitals = patient_state.get("vitals", {})
    labs = patient_state.get("labs", {})
    meds = patient_state.get("meds", [])
    
    patient_summary = f"""
    Patient Clinical Status:
    - Blood Pressure: {vitals.get('sbp')}/{vitals.get('dbp')} mmHg
    - Heart Rate: {vitals.get('hr')} bpm
    - Risk Level: {risk_level}

    Current Medications:
    """
    for med in meds:
        patient_summary += f"  • {med.get('name', 'Unknown')} {med.get('dose', '')}\n"
    
    if labs.get('creatinine_mg_dl') or labs.get('egfr') or labs.get('potassium_mmol_l'):
        patient_summary += "\nLaboratory Values:\n"
        if labs.get('creatinine_mg_dl'):
            patient_summary += f"  • Creatinine: {labs['creatinine_mg_dl']} mg/dL\n"
        if labs.get('egfr'):
            patient_summary += f"  • eGFR: {labs['egfr']} mL/min\n"
        if labs.get('potassium_mmol_l'):
            patient_summary += f"  • Potassium: {labs['potassium_mmol_l']} mmol/L\n"
    
    system_prompt = """You are an expert cardiologist specializing in heart failure medication management.

    Your task is to analyze the patient's current status and provide a medication titration recommendation based on the Heart Failure Medication Titration Protocol provided.

    CRITICAL INSTRUCTIONS:
    1. Base your recommendation STRICTLY on the protocol document provided
    2. Consider the patient's vitals, labs, current medications, and risk level
    3. If the patient's situation is NOT clearly covered by the protocol, or if you're uncertain, you MUST indicate that manual physician review is required
    4. Provide specific, actionable recommendations with clear rationale
    5. Format your response as JSON with the following structure:
    {
    "action": "titrate" | "maintain" | "hold" | "escalate",
    "recommendation_text": "Detailed recommendation for the patient",
    "new_medications": [{"name": "med_name", "dose": "dose_info"}] or null,
    "rationale": "Clinical reasoning based on protocol",
    "requires_manual_review": true | false,
    "protocol_references": "Specific sections from protocol that support this recommendation"
    }

    If requires_manual_review is true, explain why in the rationale."""
    
    user_prompt = f"""Based on the following Heart Failure Medication Titration Protocol and patient status, provide a medication recommendation.

    === PROTOCOL DOCUMENT ===
    {protocol_text}

    === PATIENT STATUS ===
    {patient_summary}

    === YOUR RECOMMENDATION ===
    Provide your recommendation in JSON format as specified."""
    
    try:
        load_dotenv()
        response = openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        result = json.loads(content)
        print(f"LLM Recommendation generated: action={result.get('action')}, manual_review={result.get('requires_manual_review')}")
        return result
        
    except Exception as e:
        print(f"Error generating LLM recommendation: {e}")
        return {
            "action": "hold",
            "recommendation_text": f"Unable to generate recommendation due to error: {str(e)}",
            "rationale": "System error occurred",
            "requires_manual_review": True
        }


@function_tool(name_override="generate_recommendation_tool")
def generate_recommendation_tool(
    wrapper: RunContextWrapper[AgentContext],
    risk_level: Literal["high", "moderate", "none"],
    current_vitals_sbp: float,
    current_vitals_dbp: float,
    current_vitals_hr: float,
    current_meds: List[MedItem],
    labs_creatinine_mg_dl: Optional[float] = None,
    labs_egfr: Optional[float] = None,
    labs_potassium_mmol_l: Optional[float] = None,
) -> RecommendationResult:
    """
    Generate medication titration recommendation using LLM with protocol document as context.
    
    The LLM analyzes the patient state against the Heart Failure Medication Titration Protocol
    and provides evidence-based recommendations. If the situation is not clearly covered by
    the protocol, it will flag for manual physician review.
    """
    patient_doc = wrapper.context.patient_doc
    if not patient_doc:
        return RecommendationResult(
            action="hold",
            recommendation_text="Unable to generate recommendation: patient context not found",
            rationale="Missing patient information"
        )
    
    print(f"generate_recommendation_tool 为患者生成建议: patient_id={patient_doc.patient_id}")
    
    # Load protocol document
    protocol_text = _load_titration_protocol()
    if not protocol_text:
        return RecommendationResult(
            action="hold",
            recommendation_text="Unable to generate recommendation: protocol document not available",
            rationale="Protocol document could not be loaded"
        )
    
    # Prepare patient state
    patient_state = {
        "vitals": {
            "sbp": current_vitals_sbp,
            "dbp": current_vitals_dbp,
            "hr": current_vitals_hr
        },
        "labs": {
            "creatinine_mg_dl": labs_creatinine_mg_dl,
            "egfr": labs_egfr,
            "potassium_mmol_l": labs_potassium_mmol_l
        },
        "meds": [m.model_dump() for m in current_meds],
        "risk_level": risk_level
    }
    
    # Generate recommendation using LLM
    llm_result = _generate_llm_recommendation(patient_state, risk_level, protocol_text)
    
    # Format recommendation text
    recommendation_text = llm_result.get("recommendation_text", "")
    
    # Add manual review notice if needed
    if llm_result.get("requires_manual_review", False):
        recommendation_text = (
            "⚠️ MANUAL PHYSICIAN REVIEW REQUIRED\n\n" + 
            recommendation_text +
            "\n\n⚠️ This case requires direct physician evaluation as it falls outside standard protocol guidelines or requires clinical judgment beyond automated assessment."
        )
    
    # Parse new medications if provided
    new_meds = None
    if llm_result.get("new_medications"):
        try:
            new_meds = [MedItem(**med) for med in llm_result["new_medications"]]
        except Exception:
            pass
    
    # Save to database
    db = get_db()
    if db:
        recommendation_data = {
            "action": llm_result.get("action", "hold"),
            "risk_level": risk_level,
            "current_vitals": {"sbp": current_vitals_sbp, "dbp": current_vitals_dbp, "hr": current_vitals_hr},
            "current_meds": [m.model_dump() for m in current_meds],
            "labs": {
                "creatinine_mg_dl": labs_creatinine_mg_dl,
                "egfr": labs_egfr,
                "potassium_mmol_l": labs_potassium_mmol_l
            },
            "new_medications": llm_result.get("new_medications"),
            "requires_manual_review": llm_result.get("requires_manual_review", False),
            "protocol_references": llm_result.get("protocol_references", ""),
            "llm_rationale": llm_result.get("rationale", "")
        }
        
        status = "pending_review" if llm_result.get("requires_manual_review") else "generated"
        
        db.create_recommendation(
            user_id=patient_doc.patient_id,
            recommendation_text=recommendation_text,
            recommendation_data=recommendation_data,
            status=status
        )
    
    return RecommendationResult(
        action=llm_result.get("action", "hold"),
        recommendation_text=recommendation_text,
        new_medications=new_meds,
        rationale=llm_result.get("rationale", "")
    )


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
            "You are a heart failure medication assistant responsible for clinical intake and risk screening.\n\n"
            "**IMPORTANT: Check for Existing Patient Data First**\n"
            "When you receive control from the receptionist, the patient context may include 'latest_patient_state' "
            "with their previous vitals, labs, symptoms, and medications.\n\n"
            "**If latest_patient_state EXISTS (returning patient):**\n"
            "1. Show all latest_patient_state info explicitly in an organized way.\n"
            "2. Ask: 'Has anything changed since your last visit, or should I proceed with the current information?'\n"
            "3. If they say 'no changes' or 'looks good' or 'proceed', use the existing data to call risk_evaluator_tool immediately.\n"
            "4. If they mention ANY changes:\n"
            "   a. Acknowledge EACH change briefly (e.g., 'Noted: heart rate 55 bpm.')\n"
            "   b. ALWAYS ask after EVERY update: 'Anything else to update?' or 'Any other changes?'\n"
            "   c. Keep asking until patient explicitly says they're done (e.g., 'that's all', 'no', 'nothing else', 'nope', 'I'm done')\n"
            "   d. Do NOT say things like 'I'll connect you with clinical team' - YOU ARE the clinical team\n"
            "   e. Do NOT summarize or say 'thank you for updates' until they confirm they're done\n"
            "   f. ONLY call risk_evaluator_tool when patient explicitly confirms no more changes\n"
            "5. CRITICAL: After EVERY single update the patient gives, you MUST ask if there are more changes. Never assume they're done.\n\n"
            "**If NO latest_patient_state (new patient):**\n"
            "1. Collect all required information:\n"
            "   - Vitals: Blood pressure (SBP/DBP), Heart rate\n"
            "   - Labs: Creatinine, eGFR, Potassium (if available)\n"
            "   - Symptoms: Any current symptoms\n"
            "   - Medications: Current heart failure medications and doses\n"
            "2. After collecting each piece of info, ask for the next one.\n"
            "3. When you think you have everything, summarize what you collected and ask: 'Is this everything, or is there anything else I should know?'\n"
            "4. ONLY call risk_evaluator_tool after patient confirms everything is complete.\n\n"
            "**After calling risk_evaluator_tool:**\n"
            "- Immediately call generate_recommendation_tool with the same patient data and risk_level.\n"
            "- The recommendation tool will generate appropriate medication guidance based on risk level.\n"
            "- Present the recommendation to the patient clearly.\n"
            "- If HIGH risk: Emphasize the need for immediate physician follow-up.\n"
            "- If MODERATE/NO risk: Explain the recommendation and next steps.\n\n"
            "**Red flags to screen for:**\n"
            "SBP<80, SBP<90 with symptoms, K+≥6.0, eGFR<20, HR<50, severe symptoms.\n\n"
            "**CRITICAL RULES:**\n"
            "1. After EVERY update from patient, you MUST ask 'Anything else to update?' - no exceptions.\n"
            "2. Never call risk_evaluator_tool until patient explicitly says they're done (e.g., 'no', 'that's all', 'nothing else').\n"
            "3. Do NOT say 'I'll connect you with clinical team' or similar - YOU are the clinical intake team.\n"
            "4. Keep responses brief when collecting updates - just acknowledge and ask for more."
        ),
        tools=[risk_evaluator_tool, generate_recommendation_tool],
    )

    intake_handoff = handoff(
        agent=agent,
        # on_handoff=on_handoff,
        # input_type=HandoffInfo,
    )

    # Main Agent (receptionist/orchestrator with handoff to HF-Intake-Agent)
    # Behavior:
    # 1) FIRST: Ask if patient is new or returning (this is critical!)
    # 2) Collect appropriate information based on patient type
    # 3) Call patient_context_tool with is_existing_patient flag
    # 4) After patient context is established, handoff to HF-Intake-Agent
    receptionist_instructions = (
        RECOMMENDED_PROMPT_PREFIX
        + "\nYou are the receptionist agent for a heart failure medication service. "
        "Your job is to identify the patient and establish their context before clinical assessment.\n\n"
        "**STEP 1: Determine Patient Type**\n"
        "- Greet the patient warmly.\n"
        "- IMPORTANT: If the patient's first message includes email, phone, or patient_id, they are clearly an EXISTING patient. Skip directly to STEP 2A.\n"
        "- Otherwise, ask: 'Have you used our service before, or is this your first time?'\n"
        "- Get a clear YES (existing) or NO (new patient) answer.\n"
        "- If unclear, ask again in a friendly way.\n\n"
        "**STEP 2A: For EXISTING Patients (is_existing_patient=True)**\n"
        "- If they already provided an identifier (email/phone/patient_id) in their first message, use it directly.\n"
        "- Otherwise, ask for at least ONE identifier:\n"
        "  • Patient ID (if they have it), OR\n"
        "  • Email address, OR\n"
        "  • Phone number\n"
        "- Once you have at least one identifier, call patient_context_tool with:\n"
        "  is_existing_patient=True\n"
        "  + the identifier(s) they provided\n"
        "- After successful loading, CHECK if the returned PatientDoc has 'latest_patient_state':\n"
        "  • If YES (has previous data): Display their current information to them in a friendly summary:\n"
        "    'Welcome back! I see from your last visit:\n"
        "     - Blood pressure: [sbp]/[dbp] mmHg\n"
        "     - Heart rate: [hr] bpm\n"
        "     - Current medications: [list meds]\n"
        "     - Symptoms: [list symptoms or 'none reported']\n"
        "     Does this look correct, or has anything changed?'\n"
        "  • If NO (no previous data): Just say 'Welcome back! Let me connect you with our clinical team.'\n"
        "- Then IMMEDIATELY handoff to HF-Intake-Agent.\n"
        "- If tool returns 'patient not found' error, politely inform them and ask if they might be a new patient.\n\n"
        "**STEP 2B: For NEW Patients (is_existing_patient=False)**\n"
        "- Collect ALL THREE mandatory fields:\n"
        "  1. Full name\n"
        "  2. Email address\n"
        "  3. Phone number\n"
        "- Ask for missing information naturally in conversation.\n"
        "- Once you have all three, call patient_context_tool with:\n"
        "  is_existing_patient=False\n"
        "  name=..., email=..., phone=...\n"
        "- If tool returns 'already registered' error, inform them their info is already in system and ask if they meant to say they're an existing patient.\n\n"
        "**STEP 3: After Successful Context Loading**\n"
        "- For NEW patients: Acknowledge creation (e.g., 'Perfect! I've created your account.'), and you should provide new created user_id back to patient explicitly\n"
        "- CRITICAL: You MUST handoff to HF-Intake-Agent. Do NOT try to handle clinical questions yourself.\n"
        "- After showing patient info (for existing) or acknowledging creation (for new), ALWAYS handoff.\n\n"
        "**Important Guidelines:**\n"
        "- Keep messages concise and friendly.\n"
        "- Do NOT reveal internal tool names or handoff mechanics to the patient.\n"
        "- Handle errors gracefully and guide the patient.\n"
        "- The is_existing_patient parameter is MANDATORY when calling patient_context_tool.\n"
        "- Your ONLY job is patient identification and context loading. All clinical work is done by HF-Intake-Agent.\n"
        "- You MUST return created user id to patient if patient is NEW patient before you handoff to HF-Intake-Agent."
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

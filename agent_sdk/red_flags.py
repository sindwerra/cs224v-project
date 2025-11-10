import json
import os
from typing import Any, Dict, List, Tuple


def _kb_path() -> str:
    """
    Resolve knowledge base rules.json path from repo.
    """
    candidates = [
        os.path.join(os.getcwd(), "knowledge_base", "rules.json"),
        os.path.join(os.path.dirname(os.getcwd()), "knowledge_base", "rules.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    # Fallback: allow running even if not found (use defaults)
    return ""


def load_rules() -> Dict[str, Any]:
    """
    Load KB rules (thresholds + medication rules). If unavailable, return defaults.
    """
    path = _kb_path()
    if path and os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    # Minimal defaults if KB missing
    return {
        "red_flags": [],
        "thresholds": {
            "blood_pressure": {"titration_range": {"sbp_min": 80}, "goal_range": {"sbp_min": 90}},
            "heart_rate": {"titration_min": 50},
        },
    }


def evaluate_red_flags(patient_state: Dict[str, Any]) -> Tuple[List[str], str]:
    """
    Evaluate KB red-flag criteria and return (flags, risk_level).
    flags: list of red-flag identifiers
    risk_level: "high" | "moderate" | "none"
    """
    vit = (patient_state.get("vitals") or {})
    labs = (patient_state.get("labs") or {})
    sym = (patient_state.get("symptoms") or []) or []

    flags: List[str] = []
    sbp = vit.get("sbp")
    hr = vit.get("hr")
    k = labs.get("potassium_mmol_l")
    egfr = labs.get("egfr")
    creatinine_increase_pct_gt_30 = labs.get("creatinine_increase_pct_gt_30") is True

    # Core KB-driven checks (aligned with docs and rules.json)
    if sbp is not None and sbp < 90 and any(s in sym for s in ["dizziness", "syncope", "lightheadedness"]):
        flags.append("symptomatic_hypotension")
    if sbp is not None and sbp < 80:
        flags.append("severe_hypotension")
    if k is not None and k > 5.5:
        flags.append("hyperkalemia_moderate")
    if k is not None and k >= 6.0:
        flags.append("hyperkalemia_severe")
    if egfr is not None and egfr < 20:
        flags.append("egfr_critical")
    if hr is not None and hr < 50:
        flags.append("bradycardia")
    if creatinine_increase_pct_gt_30:
        flags.append("creatinine_rise")

    high = {"symptomatic_hypotension", "severe_hypotension", "hyperkalemia_severe", "egfr_critical"}
    level = "high" if any(f in high for f in flags) else ("moderate" if flags else "none")
    return flags, level


def to_structured_state(
    vitals_sbp: int | None = None,
    vitals_dbp: int | None = None,
    vitals_hr: int | None = None,
    labs_creatinine_mg_dl: float | None = None,
    labs_egfr: int | None = None,
    labs_potassium_mmol_l: float | None = None,
    symptoms: List[str] | None = None,
    meds: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    """
    Helper to assemble a patient_state dict from flat fields (useful for tool calling).
    """
    return {
        "vitals": {"sbp": vitals_sbp, "dbp": vitals_dbp, "hr": vitals_hr},
        "labs": {"creatinine_mg_dl": labs_creatinine_mg_dl, "egfr": labs_egfr, "potassium_mmol_l": labs_potassium_mmol_l},
        "symptoms": symptoms or [],
        "meds": meds or [],
    }



"""
AutoGen-based Agents for UAV Engine Health Monitoring.

Agent roster:
    1. Telemetry Monitor  — ingests sensor streams, detects anomalies
    2. Digital Twin Sync  — maintains physics model, computes residuals
    3. Fault Predictor    — classifies faults, predicts RUL
    4. Maintenance Planner — generates recommendations via RAG + LLM
"""

import json
import time
from typing import Optional

import structlog

from ..event_bus import get_event_bus
from ..rag.retriever import MaintenanceRAG
from .llm_client import ask_llm

logger = structlog.get_logger()


# ── RAG singleton ──
_rag: Optional[MaintenanceRAG] = None


def get_rag() -> MaintenanceRAG:
    global _rag
    if _rag is None:
        _rag = MaintenanceRAG()
        _rag.initialize()
    return _rag


# fault.predicted fires on every anomalous tick (1 Hz). Without a cooldown each one would hit
# ChromaDB and the LLM (Groq free tier is 30 req/min). A new recommendation is produced when a
# (fault, severity) pair is first seen, then at most once per cooldown.
# ponytail: in-memory dict; move to Redis (SET NX EX) if you ever run more than one API worker.
COOLDOWN_SECONDS = 30.0
_last_handled: dict[tuple[str, str], float] = {}


MAINTENANCE_SYSTEM_PROMPT = """You are the Maintenance Planner agent for AeroTwin, a UAV turbine engine health monitoring system.

Given a detected fault type, anomaly data, and relevant maintenance procedure excerpts, generate a concise maintenance recommendation.

Your response MUST be valid JSON with these fields:
{
  "summary": "1-2 sentence plain-English summary of what's wrong and what to do",
  "urgency": "routine | urgent | emergency",
  "steps": ["step 1", "step 2", ...],
  "estimated_downtime": "X hours",
  "safety_note": "any critical safety warning or empty string"
}

Be specific, actionable, and reference the procedure documents."""


async def handle_fault_predicted(event: dict):
    """
    Maintenance Planner agent logic.

    When a fault is predicted, retrieve relevant maintenance procedures
    via RAG, then use the LLM to generate a natural-language recommendation.
    """
    data = event.get("data", {})
    fault_type = data.get("fault_type", "none")
    confidence = data.get("confidence", 0)
    rul_hours = data.get("rul_hours")
    severity = data.get("severity", "normal")

    if fault_type == "none":
        return

    key = (fault_type, severity)
    now = time.monotonic()
    if now - _last_handled.get(key, float("-inf")) < COOLDOWN_SECONDS:
        return
    _last_handled[key] = now

    # 1. RAG retrieval
    try:
        procedures = get_rag().get_procedure_for_fault(fault_type)
    except Exception as e:  # RAG is an enhancement: still issue a recommendation without it
        logger.warning("rag_unavailable", error=str(e))
        procedures = []

    # Build context from retrieved docs
    rag_context = ""
    source_docs = []
    for p in procedures[:3]:
        rag_context += f"\n--- Source: {p['source']} (relevance: {p['relevance_score']:.2f}) ---\n{p['content']}\n"
        if p["source"] not in source_docs:
            source_docs.append(p["source"])

    # 2. LLM reasoning
    user_prompt = (
        f"FAULT DETECTED: {fault_type.replace('_', ' ').title()}\n"
        f"Confidence: {confidence:.1%}\n"
        f"Severity: {severity}\n"
        f"Remaining Useful Life: {rul_hours} flight hours\n\n"
        f"RELEVANT MAINTENANCE PROCEDURES:\n{rag_context}\n\n"
        f"Generate a maintenance recommendation as JSON."
    )

    llm_response = await ask_llm(MAINTENANCE_SYSTEM_PROMPT, user_prompt)

    # 3. Parse LLM response (with fallback)
    llm_recommendation = None
    if llm_response:
        try:
            # Extract JSON from response (handle markdown code blocks)
            clean = llm_response.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            llm_recommendation = json.loads(clean)
        except (json.JSONDecodeError, IndexError):
            llm_recommendation = None
        if not isinstance(llm_recommendation, dict):  # e.g. the model returned a JSON list
            llm_recommendation = None

    # 4. Build recommendation (LLM-enhanced or fallback)
    if llm_recommendation:
        procedure_summary = llm_recommendation.get("summary", f"Fault: {fault_type}")
        priority = llm_recommendation.get("urgency", "urgent")
        steps = llm_recommendation.get("steps", [])
        downtime = llm_recommendation.get("estimated_downtime", "TBD")
        safety_note = llm_recommendation.get("safety_note", "")
    else:
        # Fallback without LLM
        procedure_summary = procedures[0]["content"][:300] if procedures else f"Schedule inspection for {fault_type}"
        priority = "emergency" if severity == "critical" else "urgent"
        steps = []
        downtime = "TBD"
        safety_note = ""

    recommendation = {
        "fault_type": fault_type,
        "confidence": confidence,
        "rul_hours": rul_hours,
        "priority": priority,
        "procedure_summary": procedure_summary,
        "steps": steps,
        "estimated_downtime": downtime,
        "safety_note": safety_note,
        "source_documents": source_docs,
        "llm_enhanced": llm_recommendation is not None,
        "message": f"[Maintenance Planner] {priority.upper()}: {fault_type.replace('_', ' ').title()} — "
                   f"RUL: {rul_hours}h. {procedure_summary[:100]}",
    }

    bus = get_event_bus()
    await bus.publish("maintenance.recommended", recommendation, agent_name="maintenance_planner")


async def setup_agent_subscriptions():
    """Wire up agent event subscriptions. Called during app startup."""
    bus = get_event_bus()
    await bus.subscribe("fault.predicted", handle_fault_predicted)

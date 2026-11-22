"""
AutoGen-based Agents for UAV Engine Health Monitoring.

Agent roster:
    1. Telemetry Monitor  — ingests sensor streams, detects anomalies
    2. Digital Twin Sync  — maintains physics model, computes residuals
    3. Fault Predictor    — classifies faults, predicts RUL
    4. Maintenance Planner — generates recommendations via RAG
"""

import json
from typing import Optional

from ..event_bus import get_event_bus
from ..rag.retriever import MaintenanceRAG


# ── RAG singleton ──
_rag: Optional[MaintenanceRAG] = None


def get_rag() -> MaintenanceRAG:
    global _rag
    if _rag is None:
        _rag = MaintenanceRAG()
        _rag.initialize()
    return _rag


async def handle_fault_predicted(event: dict):
    """
    Maintenance Planner agent logic.

    When a fault is predicted, retrieve relevant maintenance procedures
    via RAG and publish a maintenance recommendation.
    """
    data = event.get("data", {})
    fault_type = data.get("fault_type", "none")
    confidence = data.get("confidence", 0)
    rul_hours = data.get("rul_hours")
    severity = data.get("severity", "normal")

    if fault_type == "none":
        return

    # RAG retrieval
    rag = get_rag()
    procedures = rag.get_procedure_for_fault(fault_type)

    # Build recommendation
    if procedures:
        top = procedures[0]
        procedure_summary = top["content"][:500]
        source_docs = list({p["source"] for p in procedures})
    else:
        procedure_summary = f"No specific procedure found for {fault_type}. Schedule general inspection."
        source_docs = []

    # Determine priority
    if severity == "critical":
        priority = "emergency"
    elif severity == "warning":
        priority = "urgent"
    else:
        priority = "routine"

    recommendation = {
        "fault_type": fault_type,
        "confidence": confidence,
        "rul_hours": rul_hours,
        "priority": priority,
        "procedure_summary": procedure_summary,
        "source_documents": source_docs,
        "message": f"[Maintenance Planner] {priority.upper()}: {fault_type.replace('_', ' ').title()} — "
                   f"RUL: {rul_hours}h. See: {', '.join(source_docs) if source_docs else 'general inspection'}",
    }

    bus = get_event_bus()
    await bus.publish("maintenance.recommended", recommendation, agent_name="maintenance_planner")


async def setup_agent_subscriptions():
    """Wire up agent event subscriptions. Called during app startup."""
    bus = get_event_bus()
    await bus.subscribe("fault.predicted", handle_fault_predicted)

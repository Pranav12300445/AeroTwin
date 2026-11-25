"""Maintenance Planner agent: RAG + LLM recommendation, fallbacks, cooldown, wiring."""

import json
from unittest.mock import AsyncMock

import pytest

from app.agents import coordinator
from app.agents.coordinator import handle_fault_predicted, setup_agent_subscriptions


def fault_event(fault_type="bearing_wear", severity="critical", confidence=0.9, rul=12.5):
    return {"data": {"fault_type": fault_type, "confidence": confidence,
                     "rul_hours": rul, "severity": severity}}


@pytest.fixture
def published(monkeypatch):
    """Capture what the agent publishes instead of hitting Redis."""
    bus = type("FakeBus", (), {})()
    bus.calls = []

    async def publish(channel, data, agent_name="system"):
        bus.calls.append((channel, data, agent_name))

    bus.publish = publish
    bus.subscribe = AsyncMock()
    monkeypatch.setattr(coordinator, "get_event_bus", lambda: bus)
    return bus


LLM_JSON = json.dumps({
    "summary": "Bearing wear detected; inspect and replace bearings.",
    "urgency": "urgent",
    "steps": ["Rotate shaft", "Measure radial play"],
    "estimated_downtime": "6 hours",
    "safety_note": "Let the engine cool first.",
})


# ── LLM-enhanced path ──

async def test_llm_recommendation_is_published_with_all_fields(published, stub_rag, stub_llm):
    stub_llm.response = LLM_JSON
    await handle_fault_predicted(fault_event())

    channel, rec, agent = published.calls[0]
    assert (channel, agent) == ("maintenance.recommended", "maintenance_planner")
    assert rec["llm_enhanced"] is True
    assert rec["priority"] == "urgent"
    assert rec["procedure_summary"].startswith("Bearing wear detected")
    assert rec["steps"] == ["Rotate shaft", "Measure radial play"]
    assert rec["estimated_downtime"] == "6 hours"
    assert rec["safety_note"] == "Let the engine cool first."
    assert rec["fault_type"] == "bearing_wear"
    assert rec["confidence"] == 0.9
    assert rec["rul_hours"] == 12.5
    assert rec["message"].startswith("[Maintenance Planner] URGENT: Bearing Wear")


async def test_llm_json_wrapped_in_markdown_fence_is_parsed(published, stub_rag, stub_llm):
    stub_llm.response = f"```json\n{LLM_JSON}\n```"
    await handle_fault_predicted(fault_event())
    assert published.calls[0][1]["llm_enhanced"] is True
    assert published.calls[0][1]["steps"][0] == "Rotate shaft"


async def test_llm_partial_json_uses_defaults(published, stub_rag, stub_llm):
    stub_llm.response = json.dumps({"summary": "Only a summary"})
    await handle_fault_predicted(fault_event())
    rec = published.calls[0][1]
    assert rec["llm_enhanced"] is True
    assert (rec["priority"], rec["steps"], rec["estimated_downtime"], rec["safety_note"]) == ("urgent", [], "TBD", "")


async def test_prompt_contains_fault_details_and_only_top_three_procedures(published, stub_rag, stub_llm):
    stub_rag.procedures = [{"content": f"chunk-{i}", "source": f"doc{i}.md", "relevance_score": 0.5} for i in range(5)]
    await handle_fault_predicted(fault_event("fuel_nozzle_clog", "warning", 0.55, 80.0))

    system_prompt, user_prompt = stub_llm.prompts[0]
    assert "valid JSON" in system_prompt
    assert "Fuel Nozzle Clog" in user_prompt
    assert "55.0%" in user_prompt and "warning" in user_prompt and "80.0 flight hours" in user_prompt
    assert "chunk-0" in user_prompt and "chunk-2" in user_prompt
    assert "chunk-3" not in user_prompt
    assert stub_rag.calls == ["fuel_nozzle_clog"]


async def test_source_documents_are_deduplicated_in_order(published, stub_rag, stub_llm):
    stub_llm.response = LLM_JSON
    await handle_fault_predicted(fault_event())
    assert published.calls[0][1]["source_documents"] == ["bearing_inspection.md", "routine_health_check.md"]


# ── fallbacks ──

@pytest.mark.parametrize("llm_response", ["", "this is not json", "[1, 2, 3]", '"just a string"', "```\nnot json\n```"])
async def test_unusable_llm_output_falls_back_to_rag_text(published, stub_rag, stub_llm, llm_response):
    stub_llm.response = llm_response
    await handle_fault_predicted(fault_event(severity="critical"))

    rec = published.calls[0][1]
    assert rec["llm_enhanced"] is False
    assert rec["priority"] == "emergency"          # critical -> emergency
    assert rec["procedure_summary"] == stub_rag.procedures[0]["content"][:300]
    assert rec["steps"] == [] and rec["estimated_downtime"] == "TBD"


async def test_fallback_priority_is_urgent_when_not_critical(published, stub_rag, stub_llm):
    await handle_fault_predicted(fault_event(severity="warning"))
    assert published.calls[0][1]["priority"] == "urgent"


async def test_fallback_summary_truncated_to_300_chars(published, stub_rag, stub_llm):
    stub_rag.procedures = [{"content": "x" * 1000, "source": "a.md", "relevance_score": 1.0}]
    await handle_fault_predicted(fault_event())
    assert len(published.calls[0][1]["procedure_summary"]) == 300


async def test_no_procedures_and_no_llm_still_recommends_an_inspection(published, stub_rag, stub_llm):
    stub_rag.procedures = []
    await handle_fault_predicted(fault_event("turbine_erosion"))
    rec = published.calls[0][1]
    assert rec["procedure_summary"] == "Schedule inspection for turbine_erosion"
    assert rec["source_documents"] == []


async def test_rag_failure_does_not_prevent_a_recommendation(published, stub_llm, monkeypatch):
    def broken():
        raise RuntimeError("chromadb not installed")

    monkeypatch.setattr(coordinator, "get_rag", broken)
    stub_llm.response = LLM_JSON
    await handle_fault_predicted(fault_event())

    rec = published.calls[0][1]
    assert rec["llm_enhanced"] is True and rec["source_documents"] == []


async def test_fault_none_is_ignored(published, stub_rag, stub_llm):
    await handle_fault_predicted(fault_event("none"))
    assert published.calls == [] and stub_llm.prompts == []


async def test_event_without_data_is_ignored(published, stub_rag, stub_llm):
    await handle_fault_predicted({})
    assert published.calls == []


# ── cooldown (protects the Groq rate limit; fault.predicted fires at 1 Hz) ──

async def test_repeated_event_within_cooldown_is_skipped(published, stub_rag, stub_llm):
    for _ in range(5):
        await handle_fault_predicted(fault_event())
    assert len(published.calls) == 1
    assert len(stub_llm.prompts) == 1


async def test_severity_escalation_bypasses_cooldown(published, stub_rag, stub_llm):
    await handle_fault_predicted(fault_event(severity="warning"))
    await handle_fault_predicted(fault_event(severity="critical"))
    assert [c[1]["priority"] for c in published.calls] == ["urgent", "emergency"]


async def test_different_faults_do_not_share_a_cooldown(published, stub_rag, stub_llm):
    await handle_fault_predicted(fault_event("bearing_wear"))
    await handle_fault_predicted(fault_event("compressor_stall"))
    assert len(published.calls) == 2


async def test_event_is_handled_again_after_cooldown(published, stub_rag, stub_llm, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(coordinator.time, "monotonic", lambda: now[0])
    await handle_fault_predicted(fault_event())
    now[0] += coordinator.COOLDOWN_SECONDS - 1
    await handle_fault_predicted(fault_event())
    assert len(published.calls) == 1
    now[0] += 2
    await handle_fault_predicted(fault_event())
    assert len(published.calls) == 2


# ── wiring ──

async def test_setup_subscribes_planner_to_fault_predicted(published):
    await setup_agent_subscriptions()
    published.subscribe.assert_awaited_once_with("fault.predicted", handle_fault_predicted)


def test_get_rag_initializes_once(monkeypatch):
    created = []

    class FakeRAG:
        def __init__(self):
            created.append(self)
            self.initialized = 0

        def initialize(self):
            self.initialized += 1

    monkeypatch.setattr(coordinator, "MaintenanceRAG", FakeRAG)
    assert coordinator.get_rag() is coordinator.get_rag()
    assert len(created) == 1 and created[0].initialized == 1

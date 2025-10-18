from app.config import get_settings
from app.summarizer.engines.deterministic import DeterministicEngine, plural
from app.summarizer.json_path import path_exists
from app.summarizer.models import SummarizationRequest


def test_deterministic_engine_generates_bullets():
    payload = {
        "orders": [
            {"id": 1, "total": 99.5, "status": "paid"},
            {"id": 2, "total": 10.0, "status": "failed"},
            {"id": 3, "total": 17.5, "status": "paid"},
        ]
    }
    settings = get_settings()
    engine = DeterministicEngine()
    request = SummarizationRequest(
        payload=payload,
        focus=["orders"],
        engine="deterministic",
        length="medium",
        style="bullets",
    )

    bundle = engine.summarize(request, settings)
    assert bundle.bullets, "Expected at least one summary bullet."
    primary = bundle.bullets[0]
    assert "orders" in primary.text.lower()
    assert any(citation.path for citation in primary.citations)
    payload_ref = bundle.metadata["payload"]
    for bullet in bundle.bullets:
        assert bullet.citations, "Each bullet should include at least one citation."
        for citation in bullet.citations:
            assert citation.value_preview
            assert citation.value_preview_typed is not None
            assert len(citation.value_preview) <= 3
            assert path_exists(payload_ref, citation.path)
    array_bullet_texts = [
        bullet.text for bullet in bundle.bullets if "orders" in bullet.text.lower()
    ]
    concatenated = " ".join(array_bullet_texts)
    assert "avg 42.33" in concatenated
    assert 'status: "paid" (2), "failed" (1)' in concatenated


def test_deterministic_engine_redacts_sensitive_values():
    payload = {
        "users": [
            {"email": "jane@example.com", "phone": "+1-555-123-4567"},
        ]
    }
    settings = get_settings()
    engine = DeterministicEngine()
    request = SummarizationRequest(
        payload=payload,
        focus=["users"],
        engine="deterministic",
        length="short",
        style="bullets",
    )

    bundle = engine.summarize(request, settings)
    assert any("redacted" in bullet.text.lower() for bullet in bundle.bullets)


def test_mixed_type_field_summary():
    payload = {
        "items": [
            {"v": 1},
            {"v": "1"},
            {"v": True},
            {"v": 2},
        ]
    }
    settings = get_settings()
    engine = DeterministicEngine()
    request = SummarizationRequest(
        payload=payload,
        focus=["items"],
        engine="deterministic",
        length="medium",
        style="bullets",
    )

    bundle = engine.summarize(request, settings)
    items_bullet = next(
        bullet for bullet in bundle.bullets if bullet.text.lower().startswith("items:")
    )
    assert "mixed types detected" in items_bullet.text.lower()

    evidence = items_bullet.evidence["v"]
    assert evidence["type_counts"] == {"number": 2, "string": 1, "boolean": 1}
    assert "number" in evidence and "string" in evidence and "boolean" in evidence

    field_citations = [c for c in items_bullet.citations if c.path.endswith(".v")]
    assert len(field_citations) == 1
    citation = field_citations[0]
    typed_preview = {
        entry["type"]: entry["examples"] for entry in citation.value_preview_typed
    }
    assert (
        "number" in typed_preview
        and "string" in typed_preview
        and "boolean" in typed_preview
    )


def test_delta_summary_includes_changes():
    settings = get_settings()
    engine = DeterministicEngine()
    request = SummarizationRequest(
        payload={"orders": [{"total": 10}]},
        baseline_payload={"orders": [{"total": 8}]},
        engine="deterministic",
        focus=["orders"],
        length="medium",
        style="bullets",
    )
    bundle = engine.summarize(request, settings)
    delta_bullets = [
        bullet for bullet in bundle.bullets if bullet.text.startswith("Delta:")
    ]
    assert delta_bullets, "Expected delta bullet when baseline differs."
    delta_citation = delta_bullets[0].citations[0]
    assert delta_citation.value_preview


def test_plural_helper():
    assert plural(1, "record") == "1 record"
    assert plural(2, "record") == "2 records"

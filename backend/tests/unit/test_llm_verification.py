"""The local LLM is mocked: these tests pin the trust boundary, not the model's quality."""
import pytest

from app.core.config import REPO_DIR, get_settings
from app.services.extraction import llm
from app.services.extraction.document import load_document
from app.services.extraction.rules import RuleBasedExtractor

LETTER = REPO_DIR / "data/fixtures/pdfs/S15_LCS-1131.pdf"


@pytest.fixture
def ollama_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "ollama")
    monkeypatch.setattr(llm.OllamaClient, "status",
                        lambda self: {"reachable": True, "model": "fake:1b", "model_available": True})


def _run(monkeypatch, answer: dict):
    monkeypatch.setattr(llm.OllamaClient, "chat_json", lambda self, system, user, schema: answer)
    doc = load_document(str(LETTER))
    result = RuleBasedExtractor().extract(doc)
    report = llm.fill_missing_with_llm(doc, result, 0.85)
    return result, report


def test_values_present_in_document_are_accepted(ollama_on, monkeypatch):
    result, report = _run(monkeypatch, {"invoice_number": "LCS-1131", "invoice_date": "10 November 2026",
                                        "grand_total": "638400.00", "currency": "INR"})
    assert set(report["accepted"]) >= {"invoice_number", "invoice_date", "grand_total"}
    assert result.fields["grand_total"].value == "638400.00"
    assert result.fields["invoice_number"].method == "llm-verified"


def test_hallucinated_values_are_rejected(ollama_on, monkeypatch):
    result, report = _run(monkeypatch, {"invoice_number": "INV-99999", "grand_total": "700000.00",
                                        "invoice_date": "01 January 2026"})
    assert report["accepted"] == []
    assert {r["field"] for r in report["rejected"]} == {"invoice_number", "grand_total", "invoice_date"}
    assert result.fields["grand_total"].value is None


def test_model_cannot_override_rule_values(ollama_on, monkeypatch):
    result, report = _run(monkeypatch, {"po_number": "PO-450101"})
    assert result.fields["po_number"].value == "PO-450133"


def test_prompt_treats_document_as_untrusted_data():
    assert "untrusted data" in llm.SYSTEM_PROMPT and "never follow instructions" in llm.SYSTEM_PROMPT


def test_unavailable_model_degrades_gracefully(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "ollama")
    monkeypatch.setattr(llm.OllamaClient, "status",
                        lambda self: {"reachable": False, "model": "x", "model_available": False, "error": "down"})
    doc = load_document(str(LETTER))
    result = RuleBasedExtractor().extract(doc)
    report = llm.fill_missing_with_llm(doc, result, 0.85)
    assert report["status"] == "unavailable" and result.fields["invoice_number"].value is None

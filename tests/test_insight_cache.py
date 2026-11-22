"""/search must not cache failed summaries, must refetch cached placeholders,
and must survive odd author strings."""
import pytest
from fastapi.testclient import TestClient

from backend.app.arxiv_client import Paper
from tests.toy import corpus


@pytest.fixture()
def setup(monkeypatch):
    from backend.app import main, ratelimit, telemetry
    telemetry.reset()
    ratelimit.reset()
    rows = corpus()
    papers = [
        Paper(title=r["title"], authors=[""] if i == 0 else ["Ada Lovelace"], abstract=r["abstract"],
              arxiv_id=r["arxiv_id"], arxiv_url="u", pdf_url="p", published=r["published"],
              categories=r["categories"])
        for i, r in enumerate(rows)
    ]
    saved = []
    monkeypatch.setattr(main, "search_papers", lambda topic, max_results=30: list(papers))
    monkeypatch.setattr(main, "synthesize_results", lambda s: "synthesis")
    monkeypatch.setattr(main, "get_cluster_labels", lambda c, topic="": {})
    monkeypatch.setattr(main, "save_papers_and_embeddings", lambda *a, **k: None)
    monkeypatch.setattr(main, "save_insights", lambda pairs, model: saved.extend(pairs))
    return main, TestClient(main.app), saved


def test_error_placeholders_are_not_saved(setup, monkeypatch):
    main, client, saved = setup
    monkeypatch.setattr(main, "extract_insights_batch", lambda items: [
        {"index": i, "tldr": "Error", "problem": "Error", "methods": "Error", "benchmarks": "Error"}
        if i % 2 else {"index": i, "tldr": f"real {i}", "problem": "p", "methods": "m", "benchmarks": "N/A"}
        for i in range(len(items))])
    r = client.post("/search", json={"topic": "speech recognition", "max_results": 4})
    assert r.status_code == 200, r.text
    assert len(saved) == 2 and all(v["tldr"].startswith("real") for _, v in saved)


def test_failed_summary_has_no_grounding_score(setup, monkeypatch):
    main, client, _ = setup
    monkeypatch.setattr(main, "extract_insights_batch", lambda items: [
        {"index": i, "tldr": "Error", "problem": "Error", "methods": "Error", "benchmarks": "Error"}
        for i in range(len(items))])
    r = client.post("/search", json={"topic": "speech recognition", "max_results": 3})
    assert r.status_code == 200, r.text
    assert all(p["summary"]["grounding"]["score"] is None for p in r.json()["papers"])


def test_exact_repeat_returns_the_saved_answer(setup, monkeypatch):
    main, client, _ = setup
    store = {}
    monkeypatch.setattr(main, "_load_saved_answer", lambda t, k: store.get((main._topic_key(t), k)))
    monkeypatch.setattr(main, "_save_answer", lambda t, k, r: store.__setitem__((main._topic_key(t), k), __import__("json").loads(__import__("json").dumps(__import__("fastapi.encoders", fromlist=["x"]).jsonable_encoder(r)))))
    calls = []
    monkeypatch.setattr(main, "extract_insights_batch", lambda items: calls.append(1) or [
        {"index": i, "tldr": f"real {i}", "problem": "p", "methods": "m", "benchmarks": "N/A"} for i in range(len(items))])
    first = client.post("/search", json={"topic": "Speech Recognition", "max_results": 3}).json()
    again = client.post("/search", json={"topic": "  speech   recognition ", "max_results": 3}).json()
    assert len(calls) == 1
    assert again["meta"]["cache_path"] == "saved" and again["meta"]["original_cache_path"] == "cold"
    assert [p["arxiv_id"] for p in again["papers"]] == [p["arxiv_id"] for p in first["papers"]]


def test_answers_with_failed_parts_are_not_saved(setup, monkeypatch):
    main, client, _ = setup
    saved = []
    monkeypatch.setattr(main, "_load_saved_answer", lambda t, k: None)
    monkeypatch.setattr(main, "_save_answer", lambda t, k, r: saved.append(t))
    monkeypatch.setattr(main, "extract_insights_batch", lambda items: [
        {"index": i, "tldr": "Error", "problem": "Error", "methods": "Error", "benchmarks": "Error"} for i in range(len(items))])
    client.post("/search", json={"topic": "speech recognition", "max_results": 3})
    assert saved == []

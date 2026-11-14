"""API smoke test: real pipeline code, with arXiv, the LLM and Postgres stubbed."""
import pytest
from fastapi.testclient import TestClient

from backend.app.arxiv_client import Paper, _escape
from tests.toy import corpus


@pytest.fixture()
def client(monkeypatch):
    from backend.app import main, telemetry

    papers = [
        Paper(title=r["title"], authors=["Ada Lovelace", "Alan Turing"], abstract=r["abstract"],
              arxiv_id=r["arxiv_id"], arxiv_url="u", pdf_url="p", published=r["published"],
              categories=r["categories"])
        for r in corpus()
    ]
    monkeypatch.setattr(main, "search_papers", lambda topic, max_results=30: list(papers))
    monkeypatch.setattr(main, "extract_insights_batch", lambda items: [
        {"index": i, "tldr": it["title"], "problem": "N/A", "methods": "invented zebrafish method",
         "benchmarks": "N/A"} for i, it in enumerate(items)])
    monkeypatch.setattr(main, "synthesize_results", lambda s: "synthesis")
    monkeypatch.setattr(main, "get_cluster_labels", lambda c, topic="": {})
    monkeypatch.setattr(main, "save_papers_and_embeddings", lambda *a, **k: None)
    monkeypatch.setattr(main, "save_insights", lambda *a, **k: None)
    telemetry.reset()
    main._search_log.clear()
    return TestClient(main.app)


def test_search_pipeline(client):
    r = client.post("/search", json={"topic": "A survey of speech recognition", "max_results": 5})
    assert r.status_code == 200, r.text
    body = r.json()
    top = body["papers"][0]
    assert top["title"] == "A survey of speech recognition" and top["relevance_score"] == 1.0
    assert "speech" in top["matched_terms"]
    assert "zebrafish" in top["summary"]["grounding"]["unsupported"]
    assert body["meta"]["cache_path"] == "cold"
    assert len(body["graph"]["nodes"]) == 30
    assert all(n["cluster"] for n in body["graph"]["nodes"])
    scores = [p["relevance_score"] for p in body["papers"]]
    assert scores == sorted(scores, reverse=True)


def test_hybrid_flag(client, monkeypatch):
    from backend.app import config
    monkeypatch.setattr(config, "HYBRID_RETRIEVAL", True)
    r = client.post("/search", json={"topic": "federated learning", "max_results": 5})
    assert r.status_code == 200
    assert r.json()["meta"]["hybrid_retrieval"] is True
    assert all("federated" in p["title"] for p in r.json()["papers"])


def test_metrics_and_health(client):
    client.post("/search", json={"topic": "quantum computing"})
    m = client.get("/metrics").json()
    assert m["counters"]["search_total"] == 1 and m["cache_hit_rate"] == 0.0
    assert m["latency_seconds"]["search_cold"]["count"] == 1
    assert client.get("/health").json()["status"] == "ok"
    assert client.post("/search", json={"topic": "  "}).status_code == 422
    assert client.get("/nope").status_code == 404


def test_arxiv_query_escaping():
    assert _escape('ti:"x" (OR) all:y') == "ti x OR all y"
    assert _escape('""') == ""


def test_failed_llm_summaries_are_dropped(client, monkeypatch):
    from backend.app import main
    monkeypatch.setattr(main, "extract_insights_batch", lambda items: [
        {"index": i, "tldr": "Error", "problem": "Error", "methods": "Error", "benchmarks": "Error"}
        for i, _ in enumerate(items)])
    body = client.post("/search", json={"topic": "noise robustness", "max_results": 3}).json()
    assert all(p["summary"] is None for p in body["papers"])


def test_search_is_rate_limited(client, monkeypatch):
    from backend.app import config
    monkeypatch.setattr(config, "SEARCH_RATE_LIMIT", 2)
    codes = [client.post("/search", json={"topic": "noise", "max_results": 2}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_cors_allows_only_this_site(client):
    def allowed(origin):
        r = client.options("/search", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
        return r.headers.get("access-control-allow-origin") == origin
    assert allowed("https://btp-sem-07.vercel.app")
    assert allowed("https://btp-sem-07-git-main-someone.vercel.app")
    assert allowed("http://localhost:3000")
    assert not allowed("https://evil-site.vercel.app")


def test_server_errors_do_not_leak_details(client, monkeypatch):
    from backend.app import main
    def boom(_):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(main, "synthesize_results", boom)
    r = client.post("/search", json={"topic": "noise", "max_results": 2})
    assert r.status_code == 500 and "secret" not in r.text

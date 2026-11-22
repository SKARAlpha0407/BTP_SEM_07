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
    from backend.app import ratelimit
    ratelimit.reset()
    return TestClient(main.app)


def test_search_pipeline(client, monkeypatch):
    from backend.app import config
    monkeypatch.setattr(config, "DISPLAY_ORDER", "score")  # scores are sorted in this mode
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


def test_metrics_and_health(client, monkeypatch):
    from backend.app import config
    monkeypatch.setattr(config, "EXPOSE_DOCS", True)
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


def test_private_pages_hidden_from_remote_and_tunnel_visitors(client):
    # TestClient's peer is 'testclient', i.e. not this machine.
    for path in ("/metrics", "/docs", "/openapi.json"):
        assert client.get(path).status_code == 404
    local = TestClient(client.app, client=("127.0.0.1", 50000))
    assert local.get("/metrics").status_code == 200
    assert local.get("/openapi.json").status_code == 200
    assert local.get("/metrics", headers={"cf-connecting-ip": "8.8.8.8"}).status_code == 404


def test_strict_types_and_methods(client):
    for bad in ("5", 5.0, True):
        assert client.post("/search", json={"topic": "x", "max_results": bad}).status_code == 422
    assert client.get("/search").status_code == 405
    assert client.head("/health").status_code == 200


def test_cors_allows_only_known_origins(client):
    def preflight(origin):
        return client.options("/search", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
    assert preflight("http://localhost:3000").headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert preflight("https://btp-sem-07.vercel.app").status_code == 200
    assert preflight("https://btp-sem-07-abc123-team.vercel.app").status_code == 200
    assert "access-control-allow-origin" not in preflight("https://evil-demo.vercel.app").headers
    assert "access-control-allow-credentials" not in preflight("http://localhost:3000").headers


def test_openapi_documents_error_responses(client):
    local = TestClient(client.app, client=("127.0.0.1", 50000))
    spec = local.get("/openapi.json").json()
    assert set(spec["paths"]) == {"/health", "/metrics", "/search"}
    assert {"200", "404", "422", "429", "500", "503"} <= set(spec["paths"]["/search"]["post"]["responses"])


def test_fused_order_is_kept_by_default(client):
    from backend.app import main
    from backend.app.embedding_service import rank_with_cached_vectors

    topic = "speech recognition"
    papers = [Paper(title=r["title"], authors=["Ada Lovelace"], abstract=r["abstract"], arxiv_id=r["arxiv_id"],
                    arxiv_url="u", pdf_url="p", published=r["published"], categories=r["categories"])
              for r in corpus()]
    ranked, vecs = rank_with_cached_vectors(topic, papers, {})
    ranked, _ = main._hybrid_reorder(topic, ranked, vecs)
    r = client.post("/search", json={"topic": topic, "max_results": 5})
    assert r.status_code == 200, r.text
    assert [p["title"] for p in r.json()["papers"]] == [p.title for p in ranked[:5]]

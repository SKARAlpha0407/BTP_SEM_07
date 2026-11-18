"""arXiv 429 handling: pacing, cooldown, result cache, title-query skipping,
fallbacks and the per-visitor rate limit. No network and no real sleeping."""
import arxiv
import pytest
from fastapi.testclient import TestClient

from backend.app import arxiv_client, config, ratelimit
from backend.app.arxiv_client import ArxivUnavailable, Paper


def _paper(i, title):
    return Paper(title=title, authors=["A"], abstract="abs", arxiv_id=f"id{i}",
                 arxiv_url="u", pdf_url="p", published="2026-01-01", categories=["cs.CL"])


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    arxiv_client.reset_state()
    ratelimit.reset()
    monkeypatch.setattr(config, "ARXIV_MIN_INTERVAL", 0.0)
    yield
    arxiv_client.reset_state()
    ratelimit.reset()


def test_second_identical_search_uses_the_result_cache(monkeypatch):
    calls = []
    def fake_fetch(q, limit):
        calls.append(q)
        return [_paper(i, f"retrieval augmented generation study {i}") for i in range(5)]
    monkeypatch.setattr(arxiv_client, "_fetch", fake_fetch)
    first = arxiv_client.search_papers("Retrieval-Augmented Generation", 50)
    again = arxiv_client.search_papers("  retrieval augmented   generation ", 50)
    assert [p.arxiv_id for p in first] == [p.arxiv_id for p in again]
    assert len(calls) == 1  # all: only, and nothing on the repeat


def test_title_query_runs_only_when_general_results_lack_title_matches(monkeypatch):
    calls = []
    def fake_fetch(q, limit):
        calls.append(q)
        return [_paper(i, "unrelated title") for i in range(5)]
    monkeypatch.setattr(arxiv_client, "_fetch", fake_fetch)
    arxiv_client.search_papers("graph neural networks", 50)
    assert len(calls) == 2 and calls[1].startswith("ti:")


def test_title_query_failure_keeps_general_results(monkeypatch):
    def fake_fetch(q, limit):
        if q.startswith("ti:"):
            raise ArxivUnavailable("429")
        return [_paper(1, "something else")]
    monkeypatch.setattr(arxiv_client, "_fetch", fake_fetch)
    assert [p.arxiv_id for p in arxiv_client.search_papers("graph neural networks", 50)] == ["id1"]


def test_429_starts_a_cooldown_and_stops_further_requests(monkeypatch):
    attempts = []
    class Boom:
        def results(self, search):
            attempts.append(1)
            raise arxiv.HTTPError("https://export.arxiv.org", 0, 429)
    monkeypatch.setattr(arxiv_client, "_client", Boom())
    with pytest.raises(ArxivUnavailable):
        arxiv_client.search_papers("topic one", 50)
    assert len(attempts) == 1
    with pytest.raises(ArxivUnavailable):
        arxiv_client.search_papers("topic two", 50)
    assert len(attempts) == 1  # cooling down: arXiv was not contacted again


def test_failed_search_is_not_cached(monkeypatch):
    def fail(q, limit):
        raise ArxivUnavailable("down")
    monkeypatch.setattr(arxiv_client, "_fetch", fail)
    with pytest.raises(ArxivUnavailable):
        arxiv_client.search_papers("topic", 50)
    monkeypatch.setattr(arxiv_client, "_fetch", lambda q, l: [_paper(1, "topic")])
    assert arxiv_client.search_papers("topic", 50)


def test_ratelimit_window():
    assert ratelimit.check("a", 2, now=0.0) == (True, 0)
    assert ratelimit.check("a", 2, now=1.0) == (True, 0)
    allowed, wait = ratelimit.check("a", 2, now=2.0)
    assert not allowed and wait >= 1
    assert ratelimit.check("b", 2, now=2.0)[0]
    assert ratelimit.check("a", 2, now=61.5)[0]
    assert ratelimit.check("a", 0, now=0.0)[0]  # 0 disables the limit


def test_ratelimit_client_key_uses_last_forwarded_entry():
    assert ratelimit.client_key("9.9.9.9, 1.2.3.4", "10.0.0.1") == "1.2.3.4"
    assert ratelimit.client_key(None, "10.0.0.1") == "10.0.0.1"


@pytest.fixture()
def api(monkeypatch):
    from backend.app import main, telemetry
    telemetry.reset()
    monkeypatch.setattr(main, "_stale_cached_papers", lambda vec, n: [])
    return main, TestClient(main.app)


def test_search_returns_503_not_500_when_arxiv_is_unavailable(api, monkeypatch):
    main, client = api
    def down(topic, max_results=30):
        raise ArxivUnavailable("429")
    monkeypatch.setattr(main, "search_papers", down)
    r = client.post("/search", json={"topic": "retrieval augmented generation"})
    assert r.status_code == 503
    assert r.headers["retry-after"] == "60"
    assert "busy" in r.json()["detail"]


def test_search_rate_limit_returns_429_with_retry_after(api, monkeypatch):
    main, client = api
    monkeypatch.setattr(config, "SEARCH_RATE_LIMIT_PER_MIN", 2)
    monkeypatch.setattr(main, "search_papers", lambda topic, max_results=30: [])
    codes = [client.post("/search", json={"topic": "x topic"}).status_code for _ in range(3)]
    assert codes == [404, 404, 429]
    r = client.post("/search", json={"topic": "x topic"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1

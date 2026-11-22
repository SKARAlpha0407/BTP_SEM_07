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
    first = arxiv_client.search_papers("Retrieval Augmented Generation", 50)
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


def test_ratelimit_client_key_trusts_proxy_headers_only_from_loopback():
    # Through the local tunnel: use the address the tunnel reports.
    assert ratelimit.client_key({"cf-connecting-ip": "5.6.7.8", "x-forwarded-for": "1.1.1.1"}, "127.0.0.1") == "5.6.7.8"
    assert ratelimit.client_key({"x-forwarded-for": "9.9.9.9, 1.2.3.4"}, "::1") == "1.2.3.4"
    # From the network: forged headers are ignored.
    assert ratelimit.client_key({"x-forwarded-for": "spoof"}, "192.168.1.5") == "192.168.1.5"
    assert ratelimit.client_key({"cf-connecting-ip": "spoof"}, "10.0.0.1") == "10.0.0.1"
    assert ratelimit.client_key({}, None) == "unknown"


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


def test_global_search_cap(api, monkeypatch):
    main, client = api
    monkeypatch.setattr(config, "SEARCH_RATE_LIMIT_PER_MIN", 0)
    monkeypatch.setattr(config, "SEARCH_GLOBAL_LIMIT_PER_MIN", 2)
    monkeypatch.setattr(main, "search_papers", lambda topic, max_results=30: [])
    codes = [client.post("/search", json={"topic": "x topic"}).status_code for _ in range(3)]
    assert codes == [404, 404, 429]


def test_search_rate_limit_returns_429_with_retry_after(api, monkeypatch):
    main, client = api
    monkeypatch.setattr(config, "SEARCH_RATE_LIMIT_PER_MIN", 2)
    monkeypatch.setattr(main, "search_papers", lambda topic, max_results=30: [])
    codes = [client.post("/search", json={"topic": "x topic"}).status_code for _ in range(3)]
    assert codes == [404, 404, 429]
    r = client.post("/search", json={"topic": "x topic"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1


def test_cache_key_distinguishes_symbols_and_non_latin_queries(monkeypatch):
    seen = []
    def fake_fetch(q, limit):
        seen.append(q)
        return [_paper(len(seen), f"title {q}")] * 3
    monkeypatch.setattr(arxiv_client, "_fetch", fake_fetch)
    for topic in ["C++ templates", "C templates", "量子计算", "Квантовые вычисления"]:
        arxiv_client.search_papers(topic, 50)
    queried = {q for q in seen if q.startswith("all:")}
    assert len(queried) == 4  # no two topics were answered from one cache entry
    arxiv_client.search_papers("c++   TEMPLATES", 50)
    assert len([q for q in seen if q.startswith("all:")]) == 4  # same query, different case/spacing: cached


def test_cached_papers_are_independent_copies(monkeypatch):
    monkeypatch.setattr(arxiv_client, "_fetch", lambda q, l: [_paper(1, "graph neural networks")] * 3)
    first = arxiv_client.search_papers("graph neural networks", 50)
    first[0].relevance_score = 0.99
    first[0].summary = {"tldr": "mutated"}
    first[0].authors.append("Intruder")
    again = arxiv_client.search_papers("graph neural networks", 50)
    assert again[0].relevance_score is None and again[0].summary is None
    assert again[0].authors == ["A"]


def test_lock_wait_is_bounded(monkeypatch):
    monkeypatch.setattr(config, "ARXIV_LOCK_WAIT", 0.05)
    arxiv_client._lock.acquire()
    try:
        with pytest.raises(ArxivUnavailable):
            arxiv_client._fetch("all:x", 5)
    finally:
        arxiv_client._lock.release()


def test_arxiv_http_requests_have_a_timeout():
    req = arxiv_client._client._session.request
    assert req.keywords.get("timeout") == config.ARXIV_HTTP_TIMEOUT


def test_split_version():
    assert arxiv_client.split_version("2605.12335v2") == ("2605.12335", 2)
    assert arxiv_client.split_version("hep-th/9804003v1") == ("hep-th/9804003", 1)
    assert arxiv_client.split_version("hep-th/9804003") == ("hep-th/9804003", 0)


def test_versions_of_one_paper_are_merged_keeping_the_newest(monkeypatch):
    def fake_fetch(q, limit):
        a, b, c = _paper(1, "graph neural networks"), _paper(2, "graph neural networks"), _paper(3, "other")
        a.arxiv_id, b.arxiv_id, c.arxiv_id = "2605.12335v1", "2605.12335v2", "hep-th/9804003v2"
        return [a, b, c, c]
    monkeypatch.setattr(arxiv_client, "_fetch", fake_fetch)
    ids = sorted(p.arxiv_id for p in arxiv_client.search_papers("graph neural networks", 50))
    assert ids == ["2605.12335v2", "hep-th/9804003v2"]


def test_old_style_ids_keep_their_archive(monkeypatch):
    class R:
        entry_id = "http://arxiv.org/abs/hep-th/9804003v2"
        title = "T"; summary = "S"; authors = []; pdf_url = "p"; categories = ["hep-th"]
        import datetime as _d
        published = _d.datetime(1998, 4, 1)
        def get_short_id(self):
            return self.entry_id.split("arxiv.org/abs/")[-1]
    class C:
        def results(self, search):
            return [R()]
    monkeypatch.setattr(arxiv_client, "_client", C())
    assert arxiv_client._fetch("all:x", 1)[0].arxiv_id == "hep-th/9804003v2"

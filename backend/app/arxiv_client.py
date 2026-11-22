import dataclasses
import functools
import logging
import re
import threading
import time

import arxiv
import requests
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import config

logger = logging.getLogger(__name__)


@dataclass
class Paper:
    title: str
    authors: List[str]
    abstract: str
    arxiv_id: str
    arxiv_url: str
    pdf_url: str
    published: str
    categories: List[str]
    relevance_score: Optional[float] = None
    summary: Optional[dict] = None


def _escape(topic: str) -> str:
    """Make user text safe inside an arXiv query: drop quotes, parentheses and
    field-prefix colons so input cannot alter the query structure."""
    cleaned = re.sub(r'["()\\:]+', " ", topic)
    return re.sub(r"\s+", " ", cleaned).strip()


class ArxivUnavailable(Exception):
    """arXiv could not be reached or is rate-limiting this client."""


# One shared client. arXiv asks for at most one request every 3 seconds, so
# every call goes through _lock and waits out the minimum interval. The library
# is not allowed to retry: a retry after a 429 only adds load, and a failure is
# handled by the caller (cooldown, stored papers) instead.
_client = arxiv.Client(page_size=50, delay_seconds=config.ARXIV_MIN_INTERVAL, num_retries=0)
# The library calls session.get() without a timeout; a stalled connection would
# otherwise hold _lock (and every other search) forever.
_client._session.request = functools.partial(
    requests.Session.request, _client._session, timeout=config.ARXIV_HTTP_TIMEOUT
)
_lock = threading.Lock()
_last_call = 0.0
_cooldown_until = 0.0

_cache: Dict[Tuple[str, int], Tuple[float, List["Paper"]]] = {}
_cache_lock = threading.Lock()
_CACHE_MAX = 200


def _copy(papers: List["Paper"]) -> List["Paper"]:
    """Independent copies: the pipeline writes scores and summaries onto papers."""
    return [
        dataclasses.replace(p, authors=list(p.authors), categories=list(p.categories))
        for p in papers
    ]


def _cache_key(safe_query: str, max_results: int) -> Tuple[str, int]:
    """Key on the escaped query actually sent to arXiv (case- and space-insensitive),
    so 'C++' and 'C', or two non-Latin queries, never share an entry."""
    return (" ".join(safe_query.casefold().split()), max_results)


def _cache_get(key):
    ttl = config.ARXIV_CACHE_TTL_HOURS * 3600
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < ttl:
            return _copy(hit[1])
        _cache.pop(key, None)
    return None


def _cache_put(key, papers):
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX:
            oldest = min(_cache, key=lambda k: _cache[k][0])
            del _cache[oldest]
        _cache[key] = (time.monotonic(), _copy(papers))


def reset_state() -> None:
    global _last_call, _cooldown_until
    with _lock:
        _last_call = 0.0
        _cooldown_until = 0.0
    with _cache_lock:
        _cache.clear()


def _fetch(query: str, limit: int) -> List[Paper]:
    """One paced arXiv request. Raises ArxivUnavailable on 429 or any failure."""
    global _last_call, _cooldown_until
    if not _lock.acquire(timeout=config.ARXIV_LOCK_WAIT):
        raise ArxivUnavailable("too many searches are waiting for arXiv")
    try:
        now = time.monotonic()
        if now < _cooldown_until:
            raise ArxivUnavailable("arXiv is rate-limiting; cooling down")
        wait = config.ARXIV_MIN_INTERVAL - (now - _last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            search = arxiv.Search(
                query=query,
                max_results=limit,
                sort_by=arxiv.SortCriterion.Relevance,
            )
            results = []
            for result in _client.results(search):
                results.append(
                    Paper(
                        title=result.title.replace("\n", " ").strip(),
                        authors=[author.name for author in result.authors],
                        abstract=result.summary.replace("\n", " ").strip(),
                        arxiv_id=result.entry_id.split("/")[-1],
                        arxiv_url=result.entry_id,
                        pdf_url=result.pdf_url,
                        published=result.published.strftime("%Y-%m-%d"),
                        categories=result.categories,
                    )
                )
            return results
        except arxiv.HTTPError as exc:
            if getattr(exc, "status", None) == 429:
                _cooldown_until = time.monotonic() + config.ARXIV_COOLDOWN_SECONDS
                logger.warning("arXiv returned 429; pausing requests for %ss", config.ARXIV_COOLDOWN_SECONDS)
            raise ArxivUnavailable(str(exc)) from exc
        except Exception as exc:
            raise ArxivUnavailable(str(exc)) from exc
        finally:
            _last_call = time.monotonic()
    finally:
        _lock.release()


def _tier(p: Paper, norm_topic: str, topic_words: List[str]) -> int:
    norm_title = _normalize(p.title)
    # Exact title match
    if norm_title == norm_topic:
        return 0
    # Title contains all significant words
    if topic_words and all(word in norm_title for word in topic_words):
        return 1
    # Everything else
    return 2


# The title query is skipped when the general query already returned this many
# papers whose titles contain every significant word of the topic.
_TITLE_QUERY_SKIP_AT = 3


def search_papers(topic: str, max_results: int = config.ARXIV_CANDIDATES) -> List[Paper]:
    safe = _escape(topic)
    if not safe:
        return []

    norm_topic = _normalize(topic)
    key = _cache_key(safe, max_results)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    topic_words = [w for w in norm_topic.split() if len(w) > 3]

    all_results = _fetch(f"all:{safe}", max_results)

    ti_results: List[Paper] = []
    strong = sum(1 for p in all_results if _tier(p, norm_topic, topic_words) <= 1)
    if strong < _TITLE_QUERY_SKIP_AT:
        try:
            ti_results = _fetch(f'ti:"{safe}"', 10)
        except ArxivUnavailable:
            logger.warning("title query failed; using general results only")

    merged = {}
    for p in ti_results + all_results:
        merged[p.arxiv_id] = p

    papers = list(merged.values())
    papers.sort(key=lambda p: _tier(p, norm_topic, topic_words))

    if papers:
        _cache_put(key, papers)
    return papers


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
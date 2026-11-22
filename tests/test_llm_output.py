"""LLM output handling: JSON repair, index alignment, chunking, placeholders.
The Groq client is replaced by a fake; nothing leaves the machine."""
import json
from types import SimpleNamespace

import pytest

from backend.app import llm_service as L


# --- _safe_json_loads -------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ('{"t": "uses \\\\beta"}', "uses \\beta"),        # correctly escaped LaTeX stays LaTeX
    ('{"t": "uses \\beta"}', "uses \\beta"),          # raw LaTeX is repaired, not a backspace
    ('{"t": "$\\uparrow$ gain"}', "$\\uparrow$ gain"),  # \u without hex is not a unicode escape
    ('{"t": "\\frac{a}{b} and \\theta"}', "\\frac{a}{b} and \\theta"),
    ('{"t": "\\nabla f"}', "\\nabla f"),
    ('{"t": "line one\\nThe next"}', "line one\nThe next"),  # a real newline escape survives
    ('{"t": "caf\\u00e9"}', "café"),
    ('{"t": "a \\"quote\\" b"}', 'a "quote" b'),
])
def test_safe_json_loads_handles_latex_and_real_escapes(raw, expected):
    assert L._safe_json_loads(raw)["t"] == expected


def test_safe_json_loads_strips_fences_and_prose():
    assert L._safe_json_loads('```json\n{"a": 1}\n```') == {"a": 1}
    assert L._safe_json_loads('Here you go: {"a": [1, 2]} hope it helps') == {"a": [1, 2]}


# --- alignment ---------------------------------------------------------------

def _items(idxs):
    return [{"index": i, "tldr": f"T{i}"} for i in idxs]


def test_align_uses_order_when_count_matches_even_with_one_based_indexes():
    got = L._align({"papers": _items([1, 2, 3])}, 3)
    assert [g["tldr"] for g in got] == ["T1", "T2", "T3"]


def test_align_uses_declared_indexes_for_a_partial_answer():
    got = L._align({"papers": _items([2, 0])}, 3)
    assert got[0]["tldr"] == "T0" and got[1] is None and got[2]["tldr"] == "T2"


@pytest.mark.parametrize("data", [
    {"papers": _items([0, 0])},       # duplicate index, wrong count
    {"papers": _items([5, 6])},       # out of range
    {"note": "no list here"},
    "a string",
])
def test_align_rejects_ambiguous_output(data):
    assert L._align(data, 3) is None


def test_non_dict_items_are_dropped():
    got = L._align({"papers": ["junk", {"tldr": "A"}, {"tldr": "B"}]}, 2)
    assert [g["tldr"] for g in got] == ["A", "B"]


# --- placeholders ------------------------------------------------------------

def test_placeholder_detection():
    assert L.is_placeholder_insight(L._error_insight(0))
    assert L.is_placeholder_insight(L._empty_insight(0))
    assert L.is_placeholder_insight(None)
    assert not L.is_placeholder_insight({"tldr": "Real", "problem": "N/A", "methods": "N/A", "benchmarks": "N/A"})


# --- extract_insights_batch with a fake client -------------------------------

class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        content, finish = reply
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish)])


def _reply(n, offset=0):
    return json.dumps({"papers": [{"index": i, "tldr": f"P{offset + i}", "problem": "x",
                                   "methods": "y", "benchmarks": "z"} for i in range(n)]}), "stop"


def test_batches_are_chunked_and_a_failed_chunk_only_affects_itself(monkeypatch):
    fake = FakeClient([_reply(8, 0), RuntimeError("boom"), _reply(4, 16)])
    monkeypatch.setattr(L, "client", fake)
    monkeypatch.setattr(L, "INSIGHT_BATCH_SIZE", 8)
    papers = [{"title": f"t{i}", "abstract": "a"} for i in range(20)]
    out = L.extract_insights_batch(papers)
    assert len(fake.calls) == 3 and len(out) == 20
    assert [o["tldr"] for o in out[:8]] == [f"P{i}" for i in range(8)]
    assert all(L.is_placeholder_insight(o) for o in out[8:16])
    assert [o["tldr"] for o in out[16:]] == [f"P{i}" for i in range(16, 20)]


def test_truncated_completion_is_treated_as_failure(monkeypatch):
    monkeypatch.setattr(L, "client", FakeClient([('{"papers": [{"tldr": "cut', "length")]))
    out = L.extract_insights_batch([{"title": "t", "abstract": "a"}])
    assert L.is_placeholder_insight(out[0])


def test_synthesis_never_returns_none_or_leaks_errors(monkeypatch):
    monkeypatch.setattr(L, "client", FakeClient([(None, "stop")]))
    assert L.synthesize_results([{"title": "t", "summary": None}]) == L.SYNTHESIS_UNAVAILABLE
    monkeypatch.setattr(L, "client", FakeClient([RuntimeError("secret upstream detail")]))
    text = L.synthesize_results([{"title": "t", "summary": None}])
    assert "secret" not in text and text == L.SYNTHESIS_UNAVAILABLE

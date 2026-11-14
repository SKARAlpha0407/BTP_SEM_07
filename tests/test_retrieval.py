import numpy as np

from backend.app.embedders import CharNgramHashEmbedder, GloveEmbedder, get_embedder
from backend.app.grounding import grounding_report
from backend.app.hybrid import BM25, matched_terms, rrf_fuse
from eval.ir_metrics import ranks_of_targets, summarize
from eval.run_benchmark import run, write_outputs
from eval.systems import build_system
from tests.toy import corpus


def test_hash_embedder_is_normalised_and_typo_tolerant():
    e = CharNgramHashEmbedder(dim=128)
    v = e.encode(["transformer", "transformr", "banana", ""])
    assert v.shape == (4, 128)
    assert np.allclose(np.linalg.norm(v[:3], axis=1), 1.0, atol=1e-5)
    assert np.allclose(v[3], 0.0)
    assert v[0] @ v[1] > 0.5 > v[0] @ v[2]


def test_glove_embedder_oov_is_zero(tmp_path):
    f = tmp_path / "g.txt"
    f.write_text("cat 1 0 0\ndog 0 1 0\n")
    e = GloveEmbedder(str(f))
    v = e.encode(["cat dog", "zxq123"])
    assert e.dim == 3 and np.allclose(v[1], 0.0)
    assert np.allclose(v[0], [2 ** -0.5, 2 ** -0.5, 0], atol=1e-5)


def test_registry_caches():
    assert get_embedder("hash-ngram:64") is get_embedder("hash-ngram:64")


def test_bm25_prefers_matching_doc():
    b = BM25(["graph neural networks for molecules", "speech recognition with audio", "graph theory"])
    s = b.scores("neural graph networks")
    assert s.argmax() == 0 and s[1] == 0


def test_rrf():
    assert rrf_fuse([[0, 1, 2], [1, 0, 2]])[:2] in ([0, 1], [1, 0])
    assert rrf_fuse([[0, 1, 2], [1, 2, 0], [1, 0, 2]])[0] == 1


def test_matched_terms():
    assert matched_terms("Graph neural nets of AI", "Graph networks", "a neural model") == ["graph", "neural"]


def test_grounding_flags_invented_terms():
    ins = {"tldr": "Uses contrastive pretraining", "benchmarks": "ImageNet and CIFAR"}
    rep = grounding_report(ins, "Contrastive pretraining", "We pretrain with a contrastive loss on ImageNet.")
    assert "cifar" in rep["unsupported"] and "imagenet" not in rep["unsupported"]
    assert 0 < rep["score"] < 1
    assert grounding_report({"tldr": "N/A"}, "t", "a")["score"] == 1.0


def test_systems_retrieve_known_items():
    c = corpus()
    queries, docs = [r["title"] for r in c], [r["abstract"] for r in c]
    for spec in ("bm25", "hash-ngram:256", "hybrid:hash-ngram:256"):
        s = build_system(spec)
        s.index(docs)
        m = summarize(ranks_of_targets(s.score(queries), list(range(len(c)))), 10)
        assert m["recall@10"] > 0.9, (spec, m)


def test_benchmark_end_to_end(tmp_path):
    c = corpus()
    rows, timings = run(c, ["bm25", "hash-ngram:256"], ["char", "oov"], [0.1, 0.5], [1, 2], 10)
    assert len(rows) == 2 * (1 + 2 * 2 * 2)
    by = {(r["system"], r["noise"], r["intensity"]): r["ndcg@10"] for r in rows if r["seed"] == 1}
    # heavy OOV injection must hurt the lexical baseline
    assert by[("bm25", "oov", 0.5)] < by[("bm25", "clean", 0.0)]
    write_outputs(rows, timings, str(tmp_path), 10, ["char", "oov"], [0.1, 0.5],
                  {"n_docs": len(c), "seeds": [1, 2], "k": 10})
    for name in ("results.csv", "summary.json", "summary.md", "noise_char.png", "noise_oov.png"):
        assert (tmp_path / name).stat().st_size > 0

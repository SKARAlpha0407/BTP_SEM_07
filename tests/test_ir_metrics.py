import numpy as np

from eval.ir_metrics import mean_ci95, ranks_of_targets, summarize


def test_ranks_and_ties():
    scores = np.array([[0.9, 0.1, 0.2], [0.5, 0.5, 0.5], [0.3, 0.2, 0.1]])
    assert ranks_of_targets(scores, [0, 1, 2]).tolist() == [1, 3, 3]


def test_summarize():
    m = summarize(np.array([1, 2, 20]), k=10)
    assert abs(m["recall@1"] - 1 / 3) < 1e-9
    assert abs(m["recall@10"] - 2 / 3) < 1e-9
    assert abs(m["mrr"] - (1 + 0.5 + 0.05) / 3) < 1e-9
    assert abs(m["ndcg@10"] - (1 + 1 / np.log2(3)) / 3) < 1e-9


def test_ci():
    mean, ci = mean_ci95([0.5, 0.5, 0.5])
    assert mean == 0.5 and ci == 0.0
    assert mean_ci95([0.7])[1] == 0.0

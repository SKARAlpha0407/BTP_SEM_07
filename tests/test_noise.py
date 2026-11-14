import random

from eval.noise import char_noise, corrupt_queries, oov_injection, word_dropout

Q = "attention based transformers for neural machine translation tasks"


def test_zero_intensity_is_identity():
    for fn in (char_noise, word_dropout, oov_injection):
        assert fn(Q, 0.0, random.Random(1)) == Q


def test_deterministic_for_seed():
    for kind in ("char", "dropout", "oov"):
        assert corrupt_queries([Q, Q], kind, 0.3, 42) == corrupt_queries([Q, Q], kind, 0.3, 42)
        assert corrupt_queries([Q], kind, 0.5, 42) != corrupt_queries([Q], kind, 0.5, 43)


def test_char_noise_changes_expected_fraction():
    out = char_noise(Q, 0.5, random.Random(0)).split()
    changed = sum(a != b for a, b in zip(Q.split(), out))
    assert len(out) == len(Q.split()) and changed == 4


def test_dropout_never_empty():
    assert word_dropout("single", 1.0, random.Random(0)) == "single"
    assert len(word_dropout(Q, 0.5, random.Random(0)).split()) < len(Q.split())


def test_oov_tokens_have_expected_shape():
    out = oov_injection(Q, 1.0, random.Random(0)).split()
    assert all(w.startswith("zxq") and len(w) == 6 and w[3:].isdigit() for w in out)

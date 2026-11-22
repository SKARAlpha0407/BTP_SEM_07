"""Swappable embedding back-ends behind one interface.

This is the Semester-6 experimental design carried into the retrieval system:
everything downstream (ranking, cache, LLM, graph) is held fixed and only the
embedder changes. The three families from the Sem-6 report are all available:

    spec                               family
    ---------------------------------  ------------------------------------
    all-MiniLM-L6-v2 (any ST name)     contextual, WordPiece (BERT family)
    fasttext:/path/to/cc.en.300.bin    static, subword-composed (FastText)
    glove:/path/to/glove.6B.100d.txt   static, type-level lookup (GloVe)
    hash-ngram[:dim]                   FastText-style char n-gram hashing,
                                       no pretrained file needed

Every embedder returns L2-normalised float32 rows, so cosine == dot product.
Only 384-d models can be used by the live server (pgvector column size); the
offline benchmark in eval/ accepts any dimension.
"""
from __future__ import annotations

import hashlib
import re
import threading
from typing import Dict, List, Sequence

import numpy as np

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall((text or "").lower())


def l2_normalize(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, dtype=np.float32)
    if m.ndim == 1:
        m = m[None, :]
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


class Embedder:
    """Interface: name, dim, encode(texts) -> (n, dim) normalised float32."""

    name: str = "base"
    dim: int = 0
    family: str = "unknown"

    def encode(self, texts: Sequence[str]) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    # Retrieval models trained with different inputs for queries and documents
    # (e5, bge) override these; for the rest both are plain encode().
    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self.encode(texts)

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        return self.encode(texts)


class SentenceTransformerEmbedder(Embedder):
    """Contextual sentence encoder (MiniLM, bge, mpnet, ...), CPU-only.

    CPU is forced because the MPS backend on Apple Silicon aborts the process
    when two request threads encode concurrently. A lock serialises encode().
    """

    family = "contextual"

    # Input prefixes recommended on each model's card for retrieval.
    #   e5 (intfloat/e5-*):  "query: " / "passage: " on every input
    #   bge English v1.5:    an instruction before short queries, nothing on passages
    _PREFIXES = (
        ("e5-", "query: ", "passage: "),
        ("bge-", "Represent this sentence for searching relevant passages: ", ""),
    )

    def __init__(self, model_name: str):
        self.name = model_name
        self._model = None
        self._lock = threading.Lock()
        low = model_name.lower()
        self.query_prefix, self.doc_prefix = next(
            ((q, d) for key, q, d in self._PREFIXES if key in low), ("", "")
        )

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self.name, device="cpu")
        return self._model

    @property
    def dim(self) -> int:  # type: ignore[override]
        m = self._load()
        fn = getattr(m, "get_sentence_embedding_dimension", None) or getattr(
            m, "get_embedding_dimension"
        )
        return int(fn())

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        model = self._load()
        with self._lock:
            out = model.encode(
                list(texts), convert_to_numpy=True, normalize_embeddings=True,
                show_progress_bar=False,
            )
        return np.asarray(out, dtype=np.float32)

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self.encode([self.query_prefix + t for t in texts])

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        return self.encode([self.doc_prefix + t for t in texts])


class CharNgramHashEmbedder(Embedder):
    """FastText-style subword embedder with no pretrained weights.

    Each word is the sum of fixed pseudo-random vectors for its character
    n-grams (3..5, with < > boundary markers); a text is the mean of its word
    vectors. Like FastText, an unseen or misspelled word still gets a vector
    that overlaps with its neighbours' n-grams. It carries no semantics, so it
    is a robustness baseline, not a quality baseline.
    """

    family = "static-subword"

    def __init__(self, dim: int = 384, buckets: int = 1 << 18, n_min: int = 3, n_max: int = 5):
        self.dim = dim
        self.name = f"hash-ngram:{dim}"
        self._buckets = buckets
        self._n = (n_min, n_max)
        self._cache: Dict[int, np.ndarray] = {}

    def _bucket_vec(self, bucket: int) -> np.ndarray:
        v = self._cache.get(bucket)
        if v is None:
            v = np.random.default_rng(bucket).standard_normal(self.dim).astype(np.float32)
            if len(self._cache) < 200_000:
                self._cache[bucket] = v
        return v

    def _word_vec(self, word: str) -> np.ndarray:
        w = f"<{word}>"
        acc = np.zeros(self.dim, dtype=np.float32)
        count = 0
        for n in range(self._n[0], self._n[1] + 1):
            for i in range(len(w) - n + 1):
                h = int.from_bytes(hashlib.md5(w[i:i + n].encode()).digest()[:8], "little")
                acc += self._bucket_vec(h % self._buckets)
                count += 1
        return acc / count if count else acc

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        rows = np.zeros((len(texts), self.dim), dtype=np.float32)
        for r, text in enumerate(texts):
            toks = tokenize(text)
            if toks:
                rows[r] = np.mean([self._word_vec(t) for t in toks], axis=0)
        return l2_normalize(rows)


class GloveEmbedder(Embedder):
    """Mean-pooled static word vectors from a GloVe-format text file.

    OOV words contribute nothing (the Sem-6 'zero vector' behaviour).
    """

    family = "static"

    def __init__(self, path: str):
        self.name = f"glove:{path.rsplit('/', 1)[-1]}"
        self._vecs: Dict[str, np.ndarray] = {}
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                parts = line.rstrip().split(" ")
                if len(parts) < 3:
                    continue
                self._vecs[parts[0]] = np.asarray(parts[1:], dtype=np.float32)
        if not self._vecs:
            raise ValueError(f"no vectors found in {path}")
        self.dim = len(next(iter(self._vecs.values())))

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        rows = np.zeros((len(texts), self.dim), dtype=np.float32)
        for r, text in enumerate(texts):
            hits = [self._vecs[t] for t in tokenize(text) if t in self._vecs]
            if hits:
                rows[r] = np.mean(hits, axis=0)
        return l2_normalize(rows)


class FastTextEmbedder(Embedder):
    """Mean-pooled pretrained FastText (.bin, with subword n-grams) via gensim."""

    family = "static-subword"

    def __init__(self, path: str):
        from gensim.models.fasttext import load_facebook_vectors

        self.name = f"fasttext:{path.rsplit('/', 1)[-1]}"
        self._kv = load_facebook_vectors(path)
        self.dim = int(self._kv.vector_size)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        rows = np.zeros((len(texts), self.dim), dtype=np.float32)
        for r, text in enumerate(texts):
            toks = tokenize(text)
            if toks:
                rows[r] = np.mean([self._kv.get_vector(t) for t in toks], axis=0)
        return l2_normalize(rows)


_REGISTRY: Dict[str, Embedder] = {}
_REGISTRY_LOCK = threading.Lock()


def get_embedder(spec: str) -> Embedder:
    """Return a cached embedder for a spec string (see module docstring)."""
    with _REGISTRY_LOCK:
        emb = _REGISTRY.get(spec)
        if emb is None:
            if spec.startswith("hash-ngram"):
                dim = int(spec.split(":", 1)[1]) if ":" in spec else 384
                emb = CharNgramHashEmbedder(dim=dim)
            elif spec.startswith("glove:"):
                emb = GloveEmbedder(spec.split(":", 1)[1])
            elif spec.startswith("fasttext:"):
                emb = FastTextEmbedder(spec.split(":", 1)[1])
            else:
                emb = SentenceTransformerEmbedder(spec)
            _REGISTRY[spec] = emb
        return emb

# From Semester 6 to Semester 7

**Sem 6:** *Comparison of word embedding methods in NLP: classification under
textual noise* (GloVe vs FastText vs BERT on IMDb, one fixed classifier).
**Sem 7:** *Kavosh* (formerly Research Copilot), a retrieval system over arXiv built on sentence
embeddings.

## The connecting question

Sem 6 found that the embedding that wins on clean text is not the one that
survives noisy text: BERT led on clean IMDb, but under heavy out-of-vocabulary
injection its WordPiece tokeniser fragmented unknown strings and FastText
overtook it. Sem 7 deploys a BERT-family encoder (MiniLM, WordPiece) in a
setting where inputs are short, jargon-heavy and often misspelled: search
queries. So the Sem 7 research question is:

> Does the clean-accuracy versus robustness trade-off measured for
> classification in Sem 6 also hold for retrieval, and does hybrid retrieval
> remove it?

## What carries over

| Sem 6 element | Sem 7 counterpart | Where |
|---|---|---|
| Fix everything, vary only the embedding | Corpus, queries, noise and metrics fixed; only the retrieval system varies | `eval/run_benchmark.py`, `eval/systems.py` |
| GloVe (static lookup, OOV = zero vector) | `glove:<file>` mean-pooled embedder | `backend/app/embedders.py` |
| FastText (character n-grams) | `fasttext:<file.bin>` and the download-free `hash-ngram` embedder | `backend/app/embedders.py` |
| BERT (contextual, WordPiece) | `all-MiniLM-L6-v2`, `BAAI/bge-small-en-v1.5`, any SentenceTransformers model | `backend/app/embedders.py` |
| Character / word-dropout / OOV noise at 5-50% | Same three functions and intensities, applied to the query | `eval/noise.py` |
| F1 versus noise curves | nDCG@10 (also Recall@1/10, MRR) versus noise curves | `eval/results/noise_*.png` |
| t-SNE of embeddings | t-SNE of abstract embeddings by arXiv category, with silhouette score | `eval/embedding_map.py` |
| LIME word attributions | Matched query terms per result; grounding check on LLM insights | `backend/app/hybrid.py`, `backend/app/grounding.py` |

## Sem 6 future work addressed here

| Sem 6 future-work item | Status in Sem 7 |
|---|---|
| Multi-seed evaluation with confidence intervals | Done: `--seeds`, mean ± 95% interval in tables and error bars |
| Domain transfer | Done in kind: movie reviews to scientific abstracts, classification to retrieval |
| Hybrid embeddings | Done as hybrid retrieval: BM25 + dense with Reciprocal Rank Fusion (`hybrid:<model>`, `HYBRID_RETRIEVAL=1`) |
| Lighter contextual models | Done: MiniLM (6 layers) is the production encoder; larger and smaller models compare on the same axis with ms/query |
| Adversarial attacks | Not done |

## Method

- **Task:** known-item retrieval. A paper's title is the query; its abstract
  is the single relevant document; titles are not indexed. Labels are free and
  exact, at the cost of queries being cleaner and longer than real ones.
- **Noise:** applied to the query before each system tokenises it, exactly as
  noise was applied before tokenisation in Sem 6.
- **Metrics:** Recall@1, Recall@10, MRR, nDCG@10; ties are ranked
  pessimistically so a constant scorer earns nothing.
- **Seeds:** noise is re-sampled per seed; tables report mean ± 95% interval.

## Reproduce

    python -m eval.build_dataset --per-category 150
    python -m eval.run_benchmark --models all-MiniLM-L6-v2 BAAI/bge-small-en-v1.5 \
        hash-ngram bm25 hybrid:all-MiniLM-L6-v2 --seeds 42 43 44 45 46
    python -m eval.calibrate_thresholds
    python -m eval.embedding_map

Copy `eval/results/summary.md` and the PNGs into the report.

## Limitations to state in the report

- Title-as-query is a proxy; real queries are shorter and vaguer.
- `hash-ngram` has no learned semantics. It isolates the effect of subword
  composition; use pretrained FastText (`fasttext:cc.en.300.bin`) for a fair
  quality comparison.
- The live server accepts only 384-dimensional models (pgvector column); the
  offline benchmark accepts any dimension.
- The grounding check is lexical and can flag correct paraphrases.

## Industry relevance

Dense retrieval over a vector index with a lexical fallback, an LLM stage with
cached outputs, measured latency percentiles and cache hit rate, a grounding
check on generated text, and a containerised deployment are the standard
building blocks of production search and retrieval-augmented generation
systems. The noise benchmark answers a question such systems face in practice:
how much does ranking quality drop when users mistype or use unseen terms?

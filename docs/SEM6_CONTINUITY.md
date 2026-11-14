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

## Results: answering the research question

Measured on 816 arXiv papers from six categories (cs.CL, cs.LG, cs.CV, cs.IR,
cs.RO, stat.ML), five noise seeds; full tables in `eval/results/summary.md`.

| System | nDCG@10 clean | 50% char noise | 50% word dropout | 50% OOV | Loss at 50% OOV |
|---|---|---|---|---|---|
| BM25 (lexical) | 0.983 | 0.900 | 0.843 | 0.843 | -0.140 |
| Hybrid (BM25 + MiniLM, RRF) | 0.979 | 0.891 | 0.815 | 0.742 | -0.237 |
| bge-small-en-v1.5 | 0.961 | 0.804 | 0.718 | 0.607 | -0.354 |
| all-MiniLM-L6-v2 (default) | 0.950 | 0.777 | 0.698 | 0.524 | -0.426 |
| hash-ngram (subword, no semantics) | 0.301 | 0.236 | 0.224 | 0.158 | -0.143 |

**Answer, in three parts.**

1. **The Sem 6 trade-off does not reappear in the same form.** In Sem 6 the
   clean winner (BERT) lost under heavy noise. Here the lexical system (BM25)
   wins both clean and noisy, so there is no crossover to report on this task.
2. **The robustness half of the Sem 6 finding does carry over.** WordPiece
   encoders lose the most under out-of-vocabulary noise (MiniLM -0.43, bge
   -0.35 at 50%), as BERT did in Sem 6, while token-matching and subword
   systems degrade least (BM25 -0.14, hash-ngram -0.14).
3. **Hybrid retrieval reduces the gap but does not remove it.** Fusing BM25
   with MiniLM lifts MiniLM's 50% OOV score from 0.524 to 0.742 and costs
   only 0.004 on clean queries, but BM25 alone is still higher under every
   noise type.

**Why BM25 does so well here (threat to validity).** The task uses each
paper's title as the query and its abstract as the only relevant document.
78.6% of title content words also appear in the paper's own abstract
(measured on this corpus), so exact word matching is rewarded far more than it
would be for real, shorter topic queries. Read the BM25 numbers as an upper
bound for lexical matching, not as proof that dense retrieval is worse for
users.

**Other limits on these numbers.** The intervals come from five noise seeds
over the same 816 queries, so they show noise variance, not query variance; no
significance test separates close systems (BM25 0.983 vs hybrid 0.979); one
corpus of six categories; pretrained FastText and GloVe baselines were not
run.

**Implication for the product.** The live app defaults to MiniLM with hybrid
off. On this evidence `HYBRID_RETRIEVAL=1` is the safer default for noisy,
typo-prone queries; a test set of real, human-judged topic queries is the
next step before changing it.

**Cache thresholds.** The semantic cache serves only short (<= 2 word)
queries, so its thresholds were measured on two-word queries by replaying the
cache rule (`eval/calibrate_thresholds.py`): `CACHE_TOP_SCORE=0.46` and
`CACHE_STRONG_SCORE=0.41` serve 8.2% of short queries from cache with 72% of
served hits on-topic (on-topic = shares an arXiv category; base rate 35%).

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

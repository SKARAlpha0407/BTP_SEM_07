# Map clustering on 20 real topics (top 30 papers each)

Labels: primary arXiv category (coarse). Modularity: greedy (Clauset-Newman-Moore), networkx.

| Model | Method | Clusters | Multi-paper | Largest share | NMI |
|---|---|---|---|---|---|
| all-MiniLM-L6-v2 | components | 5.0 | 1.5 | 0.82 | 0.407 |
| all-MiniLM-L6-v2 | modularity, resolution 0.5 | 5.5 | 2.0 | 0.71 | 0.479 |
| all-MiniLM-L6-v2 | modularity, resolution 1.0 | 7.2 | 3.6 | 0.36 | 0.474 |
| all-MiniLM-L6-v2 | modularity, resolution 1.5 | 9.8 | 5.8 | 0.24 | 0.453 |
| all-MiniLM-L6-v2 | modularity 1.0 − components | | | | +0.068 (better on 13, worse on 6, tied 1; Wilcoxon p=0.13) |
| all-MiniLM-L6-v2 | distinct primary categories per topic | | | | 5.2 |
| BAAI/bge-small-en-v1.5 | components | 4.8 | 1.6 | 0.82 | 0.379 |
| BAAI/bge-small-en-v1.5 | modularity, resolution 0.5 | 5.7 | 2.5 | 0.64 | 0.455 |
| BAAI/bge-small-en-v1.5 | modularity, resolution 1.0 | 7.1 | 3.9 | 0.36 | 0.463 |
| BAAI/bge-small-en-v1.5 | modularity, resolution 1.5 | 9.6 | 5.5 | 0.25 | 0.441 |
| BAAI/bge-small-en-v1.5 | modularity 1.0 − components | | | | +0.084 (better on 14, worse on 6, tied 0; Wilcoxon p=0.083) |
| BAAI/bge-small-en-v1.5 | distinct primary categories per topic | | | | 5.1 |
| intfloat/e5-small-v2 | components | 4.9 | 1.6 | 0.81 | 0.366 |
| intfloat/e5-small-v2 | modularity, resolution 0.5 | 5.8 | 2.5 | 0.60 | 0.462 |
| intfloat/e5-small-v2 | modularity, resolution 1.0 | 6.8 | 3.5 | 0.39 | 0.468 |
| intfloat/e5-small-v2 | modularity, resolution 1.5 | 9.1 | 5.2 | 0.27 | 0.450 |
| intfloat/e5-small-v2 | modularity 1.0 − components | | | | +0.102 (better on 13, worse on 5, tied 2; Wilcoxon p=0.0096) |
| intfloat/e5-small-v2 | distinct primary categories per topic | | | | 5.3 |
| thenlper/gte-small | components | 4.8 | 1.4 | 0.84 | 0.351 |
| thenlper/gte-small | modularity, resolution 0.5 | 5.8 | 2.4 | 0.60 | 0.446 |
| thenlper/gte-small | modularity, resolution 1.0 | 7.2 | 3.8 | 0.38 | 0.468 |
| thenlper/gte-small | modularity, resolution 1.5 | 9.7 | 5.3 | 0.25 | 0.427 |
| thenlper/gte-small | modularity 1.0 − components | | | | +0.117 (better on 14, worse on 5, tied 1; Wilcoxon p=0.024) |
| thenlper/gte-small | distinct primary categories per topic | | | | 5.2 |

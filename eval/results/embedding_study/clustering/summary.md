# Reading-map clustering on 100 random 30-paper subsets (seed 0)

| Model | Method | Links | Clusters | Multi-paper clusters | Largest cluster share | Isolated | NMI | ARI |
|---|---|---|---|---|---|---|---|---|
| all-MiniLM-L6-v2 | components | 22.7 | 15.3 | 4.4 | 0.28 | 10.9 | 0.705 | 0.361 |
| all-MiniLM-L6-v2 | modularity | 22.7 | 15.9 | 5.1 | 0.20 | 10.9 | 0.726 | 0.384 |
| all-MiniLM-L6-v2 | modularity − components NMI | | | | | | +0.021 (Wilcoxon p=1.9e-08) | |
| BAAI/bge-small-en-v1.5 | components | 90.0 | 1.9 | 1.4 | 0.93 | 0.5 | 0.133 | 0.037 |
| BAAI/bge-small-en-v1.5 | modularity | 90.0 | 4.6 | 4.0 | 0.36 | 0.5 | 0.650 | 0.433 |
| BAAI/bge-small-en-v1.5 | modularity − components NMI | | | | | | +0.518 (Wilcoxon p=3.9e-18) | |
| intfloat/e5-small-v2 | components | 90.0 | 2.1 | 1.4 | 0.92 | 0.6 | 0.159 | 0.044 |
| intfloat/e5-small-v2 | modularity | 90.0 | 4.6 | 4.0 | 0.36 | 0.6 | 0.641 | 0.424 |
| intfloat/e5-small-v2 | modularity − components NMI | | | | | | +0.481 (Wilcoxon p=4e-18) | |
| thenlper/gte-small | components | 90.0 | 2.0 | 1.4 | 0.92 | 0.5 | 0.147 | 0.048 |
| thenlper/gte-small | modularity | 90.0 | 4.5 | 4.0 | 0.36 | 0.5 | 0.638 | 0.421 |
| thenlper/gte-small | modularity − components NMI | | | | | | +0.491 (Wilcoxon p=6.2e-18) | |

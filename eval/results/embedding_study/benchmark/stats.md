# Paired Wilcoxon tests on per-query reciprocal rank (mean over seeds)

| A | B | Condition | MRR A | MRR B | A − B | A better / B better (queries) | p |
|---|---|---|---|---|---|---|---|
| all-MiniLM-L6-v2 | bm25 | clean | 0.939 | 0.979 | -0.040 | 19 / 70 | 2.7e-07 |
| all-MiniLM-L6-v2 | bm25 | char 50% | 0.747 | 0.884 | -0.137 | 124 / 444 | 4.8e-40 |
| all-MiniLM-L6-v2 | bm25 | dropout 50% | 0.666 | 0.824 | -0.157 | 141 / 562 | 7.9e-63 |
| all-MiniLM-L6-v2 | bm25 | oov 50% | 0.493 | 0.824 | -0.331 | 67 / 693 | 2.7e-108 |
| hybrid:all-MiniLM-L6-v2 | all-MiniLM-L6-v2 | clean | 0.972 | 0.939 | +0.033 | 64 / 5 | 6.7e-10 |
| hybrid:all-MiniLM-L6-v2 | all-MiniLM-L6-v2 | char 50% | 0.870 | 0.747 | +0.123 | 476 / 58 | 3.3e-66 |
| hybrid:all-MiniLM-L6-v2 | all-MiniLM-L6-v2 | dropout 50% | 0.787 | 0.666 | +0.121 | 605 / 68 | 3.3e-84 |
| hybrid:all-MiniLM-L6-v2 | all-MiniLM-L6-v2 | oov 50% | 0.706 | 0.493 | +0.212 | 721 / 28 | 6.7e-116 |
| hybrid:all-MiniLM-L6-v2 | bm25 | clean | 0.972 | 0.979 | -0.007 | 19 / 28 | 1.3e-01 |
| hybrid:all-MiniLM-L6-v2 | bm25 | char 50% | 0.870 | 0.884 | -0.014 | 204 / 208 | 1.9e-01 |
| hybrid:all-MiniLM-L6-v2 | bm25 | dropout 50% | 0.787 | 0.824 | -0.036 | 238 / 349 | 2.2e-11 |
| hybrid:all-MiniLM-L6-v2 | bm25 | oov 50% | 0.706 | 0.824 | -0.119 | 176 / 488 | 2.5e-47 |
| BAAI/bge-small-en-v1.5 | all-MiniLM-L6-v2 | clean | 0.964 | 0.939 | +0.024 | 59 / 26 | 1.0e-04 |
| BAAI/bge-small-en-v1.5 | all-MiniLM-L6-v2 | char 50% | 0.832 | 0.747 | +0.084 | 404 / 157 | 3.0e-29 |
| BAAI/bge-small-en-v1.5 | all-MiniLM-L6-v2 | dropout 50% | 0.717 | 0.666 | +0.051 | 430 / 275 | 1.4e-15 |
| BAAI/bge-small-en-v1.5 | all-MiniLM-L6-v2 | oov 50% | 0.606 | 0.493 | +0.113 | 548 / 223 | 1.1e-41 |
| BAAI/bge-small-en-v1.5 | bm25 | clean | 0.964 | 0.979 | -0.016 | 19 / 35 | 5.8e-03 |
| BAAI/bge-small-en-v1.5 | bm25 | char 50% | 0.832 | 0.884 | -0.052 | 178 / 297 | 1.8e-10 |
| BAAI/bge-small-en-v1.5 | bm25 | dropout 50% | 0.717 | 0.824 | -0.106 | 168 / 489 | 2.8e-42 |
| BAAI/bge-small-en-v1.5 | bm25 | oov 50% | 0.606 | 0.824 | -0.218 | 111 / 615 | 6.7e-84 |
| hybrid:BAAI/bge-small-en-v1.5 | BAAI/bge-small-en-v1.5 | clean | 0.978 | 0.964 | +0.014 | 32 / 8 | 2.1e-04 |
| hybrid:BAAI/bge-small-en-v1.5 | BAAI/bge-small-en-v1.5 | char 50% | 0.900 | 0.832 | +0.068 | 341 / 69 | 8.2e-35 |
| hybrid:BAAI/bge-small-en-v1.5 | BAAI/bge-small-en-v1.5 | dropout 50% | 0.805 | 0.717 | +0.087 | 543 / 79 | 6.8e-66 |
| hybrid:BAAI/bge-small-en-v1.5 | BAAI/bge-small-en-v1.5 | oov 50% | 0.767 | 0.606 | +0.161 | 661 / 47 | 1.5e-102 |
| hybrid:BAAI/bge-small-en-v1.5 | bm25 | clean | 0.978 | 0.979 | -0.001 | 20 / 16 | 7.4e-01 |
| hybrid:BAAI/bge-small-en-v1.5 | bm25 | char 50% | 0.900 | 0.884 | +0.016 | 227 / 136 | 1.0e-04 |
| hybrid:BAAI/bge-small-en-v1.5 | bm25 | dropout 50% | 0.805 | 0.824 | -0.019 | 265 / 294 | 7.8e-04 |
| hybrid:BAAI/bge-small-en-v1.5 | bm25 | oov 50% | 0.767 | 0.824 | -0.058 | 225 / 405 | 1.9e-20 |
| intfloat/e5-small-v2 | all-MiniLM-L6-v2 | clean | 0.974 | 0.939 | +0.035 | 66 / 21 | 1.4e-06 |
| intfloat/e5-small-v2 | all-MiniLM-L6-v2 | char 50% | 0.848 | 0.747 | +0.101 | 413 / 151 | 1.6e-31 |
| intfloat/e5-small-v2 | all-MiniLM-L6-v2 | dropout 50% | 0.757 | 0.666 | +0.090 | 489 / 212 | 2.4e-34 |
| intfloat/e5-small-v2 | all-MiniLM-L6-v2 | oov 50% | 0.627 | 0.493 | +0.134 | 559 / 215 | 5.4e-42 |
| intfloat/e5-small-v2 | bm25 | clean | 0.974 | 0.979 | -0.006 | 19 / 28 | 3.2e-01 |
| intfloat/e5-small-v2 | bm25 | char 50% | 0.848 | 0.884 | -0.036 | 177 / 245 | 4.7e-06 |
| intfloat/e5-small-v2 | bm25 | dropout 50% | 0.757 | 0.824 | -0.067 | 187 / 402 | 3.6e-24 |
| intfloat/e5-small-v2 | bm25 | oov 50% | 0.627 | 0.824 | -0.197 | 114 / 597 | 3.6e-83 |
| hybrid:intfloat/e5-small-v2 | intfloat/e5-small-v2 | clean | 0.985 | 0.974 | +0.012 | 27 / 7 | 1.6e-03 |
| hybrid:intfloat/e5-small-v2 | intfloat/e5-small-v2 | char 50% | 0.907 | 0.848 | +0.059 | 293 / 71 | 1.3e-28 |
| hybrid:intfloat/e5-small-v2 | intfloat/e5-small-v2 | dropout 50% | 0.821 | 0.757 | +0.065 | 452 / 99 | 6.3e-49 |
| hybrid:intfloat/e5-small-v2 | intfloat/e5-small-v2 | oov 50% | 0.776 | 0.627 | +0.149 | 655 / 35 | 1.8e-105 |
| hybrid:intfloat/e5-small-v2 | bm25 | clean | 0.985 | 0.979 | +0.006 | 20 / 9 | 8.2e-02 |
| hybrid:intfloat/e5-small-v2 | bm25 | char 50% | 0.907 | 0.884 | +0.023 | 232 / 107 | 4.0e-08 |
| hybrid:intfloat/e5-small-v2 | bm25 | dropout 50% | 0.821 | 0.824 | -0.002 | 259 / 250 | 7.2e-01 |
| hybrid:intfloat/e5-small-v2 | bm25 | oov 50% | 0.776 | 0.824 | -0.048 | 228 / 387 | 6.4e-16 |
| thenlper/gte-small | all-MiniLM-L6-v2 | clean | 0.974 | 0.939 | +0.035 | 65 / 13 | 4.7e-08 |
| thenlper/gte-small | all-MiniLM-L6-v2 | char 50% | 0.859 | 0.747 | +0.111 | 441 / 102 | 3.0e-51 |
| thenlper/gte-small | all-MiniLM-L6-v2 | dropout 50% | 0.751 | 0.666 | +0.085 | 500 / 192 | 9.5e-41 |
| thenlper/gte-small | all-MiniLM-L6-v2 | oov 50% | 0.648 | 0.493 | +0.154 | 605 / 160 | 4.9e-67 |
| thenlper/gte-small | bm25 | clean | 0.974 | 0.979 | -0.005 | 21 / 26 | 2.7e-01 |
| thenlper/gte-small | bm25 | char 50% | 0.859 | 0.884 | -0.025 | 199 / 255 | 2.3e-03 |
| thenlper/gte-small | bm25 | dropout 50% | 0.751 | 0.824 | -0.072 | 211 / 433 | 3.0e-23 |
| thenlper/gte-small | bm25 | oov 50% | 0.648 | 0.824 | -0.177 | 132 / 579 | 8.0e-68 |
| hybrid:thenlper/gte-small | thenlper/gte-small | clean | 0.983 | 0.974 | +0.009 | 21 / 7 | 4.0e-03 |
| hybrid:thenlper/gte-small | thenlper/gte-small | char 50% | 0.910 | 0.859 | +0.051 | 292 / 92 | 6.6e-23 |
| hybrid:thenlper/gte-small | thenlper/gte-small | dropout 50% | 0.821 | 0.751 | +0.070 | 489 / 109 | 6.4e-51 |
| hybrid:thenlper/gte-small | thenlper/gte-small | oov 50% | 0.784 | 0.648 | +0.137 | 623 / 67 | 3.5e-92 |
| hybrid:thenlper/gte-small | bm25 | clean | 0.983 | 0.979 | +0.004 | 21 / 10 | 3.1e-01 |
| hybrid:thenlper/gte-small | bm25 | char 50% | 0.910 | 0.884 | +0.026 | 240 / 105 | 9.2e-11 |
| hybrid:thenlper/gte-small | bm25 | dropout 50% | 0.821 | 0.824 | -0.003 | 298 / 254 | 9.7e-01 |
| hybrid:thenlper/gte-small | bm25 | oov 50% | 0.784 | 0.824 | -0.040 | 236 / 363 | 1.8e-12 |
| char-tfidf | bm25 | clean | 0.976 | 0.979 | -0.003 | 14 / 19 | 3.4e-01 |
| char-tfidf | bm25 | char 50% | 0.954 | 0.884 | +0.070 | 264 / 48 | 1.9e-32 |
| char-tfidf | bm25 | dropout 50% | 0.806 | 0.824 | -0.018 | 210 / 320 | 1.8e-06 |
| char-tfidf | bm25 | oov 50% | 0.803 | 0.824 | -0.021 | 213 / 307 | 7.5e-06 |

# Relative nDCG@10 loss at 50% noise

| System | char | dropout | oov |
|---|---|---|---|
| all-MiniLM-L6-v2 | 18.2% | 26.5% | 44.9% |
| BAAI/bge-small-en-v1.5 | 12.2% | 23.6% | 34.7% |
| intfloat/e5-small-v2 | 11.5% | 20.4% | 33.4% |
| thenlper/gte-small | 10.4% | 20.8% | 31.0% |
| bm25 | 8.5% | 14.3% | 14.2% |
| char-tfidf | 1.9% | 15.5% | 15.8% |
| hybrid:all-MiniLM-L6-v2 | 8.9% | 16.8% | 24.2% |
| hybrid:BAAI/bge-small-en-v1.5 | 6.8% | 15.7% | 19.1% |
| hybrid:intfloat/e5-small-v2 | 6.8% | 14.6% | 18.9% |
| hybrid:thenlper/gte-small | 6.2% | 14.3% | 17.7% |

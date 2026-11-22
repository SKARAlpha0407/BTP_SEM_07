# Short topic queries (816 per style, pool 50 by BM25, top 5)

Topical base rate (random pair shares a category): 0.349

| Model | Style | Variant | hit@1 | MRR@5 | nDCG@5 | recall@5 | topical P@5 |
|---|---|---|---|---|---|---|---|
| all-MiniLM-L6-v2 | first2 | dense | 0.542 | 0.596 | 0.616 | 0.673 | 0.589 |
| all-MiniLM-L6-v2 | first2 | hybrid_A | 0.636 | 0.721 | 0.759 | 0.873 | 0.603 |
| all-MiniLM-L6-v2 | first2 | hybrid_B | 0.615 | 0.718 | 0.757 | 0.873 | 0.603 |
| all-MiniLM-L6-v2 | idf3 | dense | 0.695 | 0.772 | 0.801 | 0.886 | 0.656 |
| all-MiniLM-L6-v2 | idf3 | hybrid_A | 0.735 | 0.824 | 0.861 | 0.973 | 0.670 |
| all-MiniLM-L6-v2 | idf3 | hybrid_B | 0.859 | 0.909 | 0.925 | 0.973 | 0.670 |
| BAAI/bge-small-en-v1.5 | first2 | dense | 0.623 | 0.661 | 0.678 | 0.729 | 0.601 |
| BAAI/bge-small-en-v1.5 | first2 | hybrid_A | 0.727 | 0.783 | 0.810 | 0.893 | 0.606 |
| BAAI/bge-small-en-v1.5 | first2 | hybrid_B | 0.685 | 0.763 | 0.796 | 0.893 | 0.606 |
| BAAI/bge-small-en-v1.5 | idf3 | dense | 0.760 | 0.814 | 0.834 | 0.896 | 0.665 |
| BAAI/bge-small-en-v1.5 | idf3 | hybrid_A | 0.789 | 0.858 | 0.888 | 0.979 | 0.672 |
| BAAI/bge-small-en-v1.5 | idf3 | hybrid_B | 0.879 | 0.921 | 0.936 | 0.979 | 0.672 |
| intfloat/e5-small-v2 | first2 | dense | 0.735 | 0.756 | 0.763 | 0.787 | 0.590 |
| intfloat/e5-small-v2 | first2 | hybrid_A | 0.803 | 0.837 | 0.852 | 0.901 | 0.597 |
| intfloat/e5-small-v2 | first2 | hybrid_B | 0.734 | 0.797 | 0.823 | 0.901 | 0.597 |
| intfloat/e5-small-v2 | idf3 | dense | 0.839 | 0.877 | 0.891 | 0.935 | 0.643 |
| intfloat/e5-small-v2 | idf3 | hybrid_A | 0.859 | 0.905 | 0.925 | 0.984 | 0.652 |
| intfloat/e5-small-v2 | idf3 | hybrid_B | 0.917 | 0.945 | 0.955 | 0.984 | 0.652 |
| thenlper/gte-small | first2 | dense | 0.654 | 0.703 | 0.721 | 0.776 | 0.604 |
| thenlper/gte-small | first2 | hybrid_A | 0.744 | 0.800 | 0.824 | 0.897 | 0.602 |
| thenlper/gte-small | first2 | hybrid_B | 0.705 | 0.780 | 0.809 | 0.897 | 0.602 |
| thenlper/gte-small | idf3 | dense | 0.806 | 0.853 | 0.872 | 0.929 | 0.660 |
| thenlper/gte-small | idf3 | hybrid_A | 0.831 | 0.889 | 0.913 | 0.987 | 0.664 |
| thenlper/gte-small | idf3 | hybrid_B | 0.907 | 0.942 | 0.954 | 0.987 | 0.664 |

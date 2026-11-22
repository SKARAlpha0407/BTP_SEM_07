# Short topic queries (816 per style, pool = all 816 papers, top 5)

Topical base rate (random pair shares a category): 0.349

| Model | Style | Variant | hit@1 | MRR@5 | nDCG@5 | recall@5 | topical P@5 |
|---|---|---|---|---|---|---|---|
| all-MiniLM-L6-v2 | first2 | dense | 0.439 | 0.479 | 0.496 | 0.547 | 0.580 |
| all-MiniLM-L6-v2 | first2 | hybrid_A | 0.549 | 0.620 | 0.652 | 0.751 | 0.604 |
| all-MiniLM-L6-v2 | first2 | hybrid_B | 0.529 | 0.616 | 0.650 | 0.751 | 0.604 |
| all-MiniLM-L6-v2 | idf3 | dense | 0.610 | 0.681 | 0.709 | 0.795 | 0.655 |
| all-MiniLM-L6-v2 | idf3 | hybrid_A | 0.650 | 0.747 | 0.789 | 0.919 | 0.678 |
| all-MiniLM-L6-v2 | idf3 | hybrid_B | 0.799 | 0.849 | 0.867 | 0.919 | 0.678 |
| BAAI/bge-small-en-v1.5 | first2 | dense | 0.533 | 0.566 | 0.579 | 0.616 | 0.580 |
| BAAI/bge-small-en-v1.5 | first2 | hybrid_A | 0.632 | 0.680 | 0.702 | 0.772 | 0.611 |
| BAAI/bge-small-en-v1.5 | first2 | hybrid_B | 0.613 | 0.674 | 0.699 | 0.772 | 0.611 |
| BAAI/bge-small-en-v1.5 | idf3 | dense | 0.694 | 0.741 | 0.761 | 0.819 | 0.664 |
| BAAI/bge-small-en-v1.5 | idf3 | hybrid_A | 0.719 | 0.794 | 0.829 | 0.936 | 0.676 |
| BAAI/bge-small-en-v1.5 | idf3 | hybrid_B | 0.827 | 0.871 | 0.888 | 0.936 | 0.676 |
| intfloat/e5-small-v2 | first2 | dense | 0.675 | 0.696 | 0.704 | 0.729 | 0.580 |
| intfloat/e5-small-v2 | first2 | hybrid_A | 0.744 | 0.776 | 0.790 | 0.836 | 0.603 |
| intfloat/e5-small-v2 | first2 | hybrid_B | 0.707 | 0.756 | 0.776 | 0.836 | 0.603 |
| intfloat/e5-small-v2 | idf3 | dense | 0.799 | 0.834 | 0.848 | 0.887 | 0.638 |
| intfloat/e5-small-v2 | idf3 | hybrid_A | 0.826 | 0.872 | 0.893 | 0.957 | 0.657 |
| intfloat/e5-small-v2 | idf3 | hybrid_B | 0.886 | 0.915 | 0.926 | 0.957 | 0.657 |
| thenlper/gte-small | first2 | dense | 0.555 | 0.598 | 0.614 | 0.662 | 0.589 |
| thenlper/gte-small | first2 | hybrid_A | 0.657 | 0.710 | 0.735 | 0.810 | 0.610 |
| thenlper/gte-small | first2 | hybrid_B | 0.638 | 0.707 | 0.733 | 0.810 | 0.610 |
| thenlper/gte-small | idf3 | dense | 0.745 | 0.792 | 0.809 | 0.863 | 0.663 |
| thenlper/gte-small | idf3 | hybrid_A | 0.777 | 0.840 | 0.869 | 0.957 | 0.669 |
| thenlper/gte-small | idf3 | hybrid_B | 0.864 | 0.903 | 0.916 | 0.957 | 0.669 |

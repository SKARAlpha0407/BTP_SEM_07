# Grounding check on 300 papers (seed 7)

Faithful summaries (copied from the abstract): mean score 1.000, 0.0% have any flagged term, 0.0% fall under the 50% line.

| Injected terms | Recall of injected terms | Mean score | Under 50% line | ROC AUC vs faithful |
|---|---|---|---|---|
| 1 | 0.997 | 0.980 | 0.0% | 0.998 |
| 2 | 0.998 | 0.961 | 0.0% | 1.000 |
| 3 | 0.997 | 0.943 | 0.0% | 1.000 |
| 5 | 0.997 | 0.909 | 0.0% | 1.000 |

Stored LLM summaries in the local database (n=159): mean score 0.699, median 0.714, 6.9% under the 50% line, 100.0% with any flagged term.

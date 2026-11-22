"""LaTeX tables for the report, read from eval/results/embedding_study/.

    python -m eval.report_tables   # writes report/Chapters/tables/*.tex
"""
import json
import os

R = "eval/results/embedding_study"
OUT = "report/Chapters/tables"
NAME = {"all-MiniLM-L6-v2": "MiniLM", "BAAI/bge-small-en-v1.5": "bge-small", "intfloat/e5-small-v2": "e5-small",
        "thenlper/gte-small": "gte-small", "bm25": "BM25", "char-tfidf": "char TF-IDF"}
MODELS = ["all-MiniLM-L6-v2", "BAAI/bge-small-en-v1.5", "intfloat/e5-small-v2", "thenlper/gte-small"]


def nm(s):
    if s.startswith("hybrid:"):
        return NAME[s.split(":", 1)[1]] + " + BM25"
    return NAME[s]


def write(name, body):
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, name + ".tex"), "w").write(body)


def benchmark():
    s = json.load(open(f"{R}/benchmark/summary.json"))["systems"]
    rows = {}
    import csv
    for r in csv.DictReader(open(f"{R}/benchmark/results.csv")):
        if r["noise"] == "clean":
            rows[r["system"]] = r
    order = MODELS + ["bm25", "char-tfidf"] + [f"hybrid:{m}" for m in MODELS]
    lines = [r"\begin{tabular}{|l|c|c|c|c|c|c|c|}", r"\hline",
             r"\textbf{System} & \textbf{R@1} & \textbf{MRR} & \textbf{nDCG@10} & \multicolumn{3}{c|}{\textbf{nDCG@10 at 50\% noise}} \\",
             r" & \multicolumn{3}{c|}{clean} & char & dropout & OOV \\", r"\hline"]
    lines[2] = r"\textbf{System} & \multicolumn{3}{c|}{\textbf{Clean}} & \multicolumn{3}{c|}{\textbf{nDCG@10, 50\% noise}} \\"
    lines[3] = r" & R@1 & MRR & nDCG@10 & char & dropout & OOV \\"
    lines = [r"\begin{tabular}{|l|c|c|c|c|c|c|}"] + lines[1:]
    for i, sname in enumerate(order):
        r, v = rows[sname], s[sname]
        n = v["noise"]
        cell = lambda k: f"{n[k]['0.5']['mean']:.3f} $\\pm$ {n[k]['0.5']['ci95']:.3f}"
        lines.append(f"{nm(sname)} & {float(r['recall@1']):.3f} & {float(r['mrr']):.3f} & {float(r['ndcg@10']):.3f} & "
                     f"{cell('char')} & {cell('dropout')} & {cell('oov')} \\\\")
        if i in (3, 5):
            lines.append(r"\hline")
    lines += [r"\hline", r"\end{tabular}"]
    write("benchmark", "\n".join(lines) + "\n")
    st = json.load(open(f"{R}/benchmark/stats.json"))["relative_loss_at_50pct"]
    lines = [r"\begin{tabular}{|l|c|c|c|}", r"\hline", r"\textbf{System} & \textbf{char} & \textbf{dropout} & \textbf{OOV} \\", r"\hline"]
    for sname in order:
        v = st[sname]
        lines.append(f"{nm(sname)} & {100*v['char']:.1f}\\% & {100*v['dropout']:.1f}\\% & {100*v['oov']:.1f}\\% \\\\")
    lines += [r"\hline", r"\end{tabular}"]
    write("relative_loss", "\n".join(lines) + "\n")


def short_queries():
    for tag in ("short_queries_fullpool", "short_queries"):
        d = json.load(open(f"{R}/{tag}/results.json"))
        rows = {(r["model"], r["style"], r["variant"]): r for r in d["rows"]}
        lines = [r"\begin{tabular}{|l|c|c|c|c|c|c|}", r"\hline",
                 r"\textbf{Model} & \multicolumn{3}{c|}{\textbf{Two-word topics (MRR@5)}} & \multicolumn{3}{c|}{\textbf{Three distinctive words (MRR@5)}} \\",
                 r" & dense & fused & re-sorted & dense & fused & re-sorted \\", r"\hline"]
        for m in MODELS:
            c = [rows[(m, st, v)]["mrr@5"] for st in ("first2", "idf3") for v in ("dense", "hybrid_B", "hybrid_A")]
            lines.append(f"{NAME[m]} & " + " & ".join(f"{x:.3f}" for x in c) + r" \\")
        lines += [r"\hline", r"\end{tabular}"]
        write(tag, "\n".join(lines) + "\n")


def latency():
    d = json.load(open(f"{R}/latency/results.json"))
    lines = [r"\begin{tabular}{|l|c|c|c|c|c|}", r"\hline",
             r"\textbf{Model} & \textbf{Load (s)} & \textbf{Memory (MB)} & \textbf{Disk (MB)} & \textbf{816 abstracts (s)} & \textbf{Query, median (ms)} \\", r"\hline"]
    for r in d["rows"]:
        lines.append(f"{NAME[r['model']]} & {r['load_seconds']:.1f} & {r['rss_increase_mb']:.0f} & {r['disk_mb']:.0f} & "
                     f"{r['encode_816_abstracts_seconds']:.1f} & {r['query_ms_median']:.1f} \\\\")
    lines += [r"\hline", r"\end{tabular}"]
    write("latency", "\n".join(lines) + "\n")


def thresholds():
    lines = [r"\begin{tabular}{|l|c|c|c|c|c|}", r"\hline",
             r"\textbf{Model} & \textbf{Measured thresholds} & \multicolumn{2}{c|}{\textbf{Measured: held-out}} & \multicolumn{2}{c|}{\textbf{Shipped 0.40/0.35}} \\",
             r" & top / strong & served & on-topic & served & on-topic \\", r"\hline"]
    for m in MODELS:
        d = json.load(open(f"{R}/thresholds/{m.replace('/', '_')}.json"))
        c, s = d["short_query"]["cache_replay"], d["suggested"]
        lines.append(f"{NAME[m]} & {s['CACHE_TOP_SCORE']:.2f} / {s['CACHE_STRONG_SCORE']:.2f} & {100*c['served_fraction']:.1f}\\% & "
                     f"{100*c['served_hits_on_topic']:.1f}\\% & {100*c['shipped_defaults']['served_fraction']:.1f}\\% & "
                     f"{100*c['shipped_defaults']['served_hits_on_topic']:.1f}\\% \\\\")
    lines += [r"\hline", r"\end{tabular}"]
    write("thresholds", "\n".join(lines) + "\n")


def clustering():
    c = json.load(open(f"{R}/clustering/results.json"))["results"]
    r = json.load(open(f"{R}/clustering_real/results.json"))["results"]
    lines = [r"\begin{tabular}{|l|c|c|c|c|c|c|}", r"\hline",
             r"\textbf{Model} & \multicolumn{3}{c|}{\textbf{Corpus subsets (100)}} & \multicolumn{3}{c|}{\textbf{Real topics (20)}} \\",
             r" & NMI comp. & NMI mod. & largest (comp./mod.) & NMI comp. & NMI mod. & largest (comp./mod.) \\", r"\hline"]
    for m in MODELS:
        a, b = c[m], r[m]
        lines.append(f"{NAME[m]} & {a['components']['nmi']:.3f} & {a['modularity']['nmi']:.3f} & "
                     f"{a['components']['largest']:.2f} / {a['modularity']['largest']:.2f} & "
                     f"{b['components@1.0']['nmi']:.3f} & {b['modularity@1.0']['nmi']:.3f} & "
                     f"{b['components@1.0']['largest']:.2f} / {b['modularity@1.0']['largest']:.2f} \\\\")
    lines += [r"\hline", r"\end{tabular}"]
    write("clustering", "\n".join(lines) + "\n")


if __name__ == "__main__":
    benchmark(); short_queries(); latency(); thresholds(); clustering()
    print("tables written to", OUT)

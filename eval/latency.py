"""Running cost of each embedding model on this machine (CPU only).

Each model is measured in a fresh process so load time and memory are not
affected by models loaded earlier:
  - load time and resident-memory increase after loading;
  - size of the downloaded model files;
  - time to encode the 816 corpus abstracts as documents (batch 64);
  - latency of encoding one short query, over 200 queries after 20 warm-up calls
    (median and 95th percentile).

    python -m eval.latency --models all-MiniLM-L6-v2 BAAI/bge-small-en-v1.5 \\
        intfloat/e5-small-v2 thenlper/gte-small
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys

OUT = "eval/results/embedding_study/latency"

CHILD = r"""
import json, os, sys, time
import numpy as np, psutil
sys.path.insert(0, os.getcwd())
from eval.data import load_corpus
spec = sys.argv[1]
proc = psutil.Process()
rss0 = proc.memory_info().rss
t0 = time.perf_counter()
from backend.app.embedders import get_embedder
emb = get_embedder(spec)
emb.encode_queries(["warm up"])
load_s = time.perf_counter() - t0
rss1 = proc.memory_info().rss
corpus = load_corpus("eval/data/corpus.jsonl")
docs = [r["abstract"] for r in corpus]
t0 = time.perf_counter()
for i in range(0, len(docs), 64):
    emb.encode_documents(docs[i:i + 64])
docs_s = time.perf_counter() - t0
queries = [" ".join(r["title"].split()[:3]) for r in corpus[:220]]
for q in queries[:20]:
    emb.encode_queries([q])
lat = []
for q in queries[20:220]:
    t = time.perf_counter(); emb.encode_queries([q]); lat.append(time.perf_counter() - t)
print(json.dumps({"model": spec, "load_seconds": load_s, "rss_increase_mb": (rss1 - rss0) / 2**20,
                  "encode_816_abstracts_seconds": docs_s,
                  "query_ms_median": 1000 * float(np.median(lat)), "query_ms_p95": 1000 * float(np.percentile(lat, 95))}))
"""


def model_dir_size(spec):
    if "/" not in spec:
        spec = "sentence-transformers/" + spec
    path = os.path.expanduser("~/.cache/huggingface/hub/models--" + spec.replace("/", "--"))
    total = 0
    for root, _, files in os.walk(os.path.join(path, "blobs")):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total / 2**20


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", required=True)
    args = ap.parse_args()
    env = dict(os.environ, TOKENIZERS_PARALLELISM="false")
    rows = []
    load_start = [round(x, 2) for x in os.getloadavg()]
    for spec in args.models:
        out = subprocess.run([sys.executable, "-c", CHILD, spec], capture_output=True, text=True, env=env, check=True)
        row = json.loads(out.stdout.strip().splitlines()[-1])
        row["disk_mb"] = model_dir_size(spec)
        rows.append(row)
        print(row, flush=True)
    import psutil
    machine = {"platform": platform.platform(), "processor": platform.processor(), "machine": platform.machine(),
               "cpu_count": os.cpu_count(), "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
               "python": platform.python_version(),
               "load_average_1_5_15min_at_end": [round(x, 2) for x in os.getloadavg()]}
    machine["load_average_1_5_15min_at_start"] = load_start
    try:
        machine["cpu_brand"] = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True,
                                              text=True).stdout.strip()
    except Exception:
        pass
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "results.json"), "w") as fh:
        json.dump({"machine": machine, "rows": rows}, fh, indent=2)
    lines = [f"# Running cost on {machine.get('cpu_brand') or machine['processor']} ({machine['ram_gb']} GB RAM)", "",
             "| Model | Load (s) | Memory added (MB) | Files on disk (MB) | Encode 816 abstracts (s) | Query median (ms) | Query p95 (ms) |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['model']} | {r['load_seconds']:.1f} | {r['rss_increase_mb']:.0f} | {r['disk_mb']:.0f} | "
                     f"{r['encode_816_abstracts_seconds']:.1f} | {r['query_ms_median']:.1f} | {r['query_ms_p95']:.1f} |")
    with open(os.path.join(OUT, "summary.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())

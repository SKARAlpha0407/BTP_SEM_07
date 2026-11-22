"""First-search latency of the running app, and pre-warming demo topics.

  python -m eval.first_search measure   # 5 new topics through POST /search
  python -m eval.first_search prewarm   # search the start-page example topics

`measure` sends each topic once to the local backend (it must be running) and
records the wall time and cache path, then reads the per-stage timings from
/metrics (these cover every search since the server last started). It calls
arXiv and the LLM, so it is run sparingly.

`prewarm` searches the five example topics shown on the start page so their
papers, embeddings and summaries are stored and their complete answers are
saved. Saved answers expire after ANSWER_CACHE_HOURS (6 h by default), so run
it within that window before a demo; stored summaries do not expire.
"""
from __future__ import annotations

import json
import os
import sys
import time

import requests

API = os.environ.get("KAVOSH_API", "http://127.0.0.1:8000")
OUT = "eval/results/embedding_study/first_search"
NEW_TOPICS = ["speculative decoding", "audio source separation", "visual question answering",
              "graph transformers for molecules", "federated learning with differential privacy"]
DEMO_TOPICS = ["retrieval augmented generation", "diffusion models for video", "graph neural networks",
               "LLM evaluation", "vision transformers"]


def search(topic):
    t = time.perf_counter()
    r = requests.post(f"{API}/search", json={"topic": topic, "max_results": 5}, timeout=300)
    wall = time.perf_counter() - t
    meta = r.json().get("meta", {}) if r.ok else {}
    return {"topic": topic, "status": r.status_code, "wall_seconds": round(wall, 2),
            "cache_path": meta.get("cache_path"), "server_seconds": meta.get("latency_seconds")}


def measure():
    rows = []
    for t in NEW_TOPICS:
        rows.append(search(t))
        print(rows[-1], flush=True)
        time.sleep(4)
    m = requests.get(f"{API}/metrics", timeout=30).json()
    stages = {k: v for k, v in m.get("latency_seconds", {}).items() if k.startswith("stage_") or k.startswith("search_")}
    walls = sorted(r["wall_seconds"] for r in rows if r["status"] == 200)
    out = {"rows": rows, "median_wall_seconds": walls[len(walls) // 2] if walls else None,
           "metrics_since_server_start": {"uptime_seconds": m.get("uptime_seconds"), "stages": stages}}
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, "results.json"), "w"), indent=2)
    print(json.dumps(out["metrics_since_server_start"], indent=2))


def prewarm():
    rows = [search(t) for t in DEMO_TOPICS]
    for r in rows:
        print(r)
    again = [search(t) for t in DEMO_TOPICS]
    for r in again:
        print("repeat:", r)


if __name__ == "__main__":
    {"measure": measure, "prewarm": prewarm}[sys.argv[1] if len(sys.argv) > 1 else "measure"]()

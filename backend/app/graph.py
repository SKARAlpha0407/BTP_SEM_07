"""Reading-map construction: nodes, weighted links and clusters.

Kept apart from the request handler so the evaluation scripts can run exactly
the same code for every embedding model.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

import numpy as np

# Link weight = W_SIM * abstract cosine + W_CAT * category Jaccard + W_AUTH * shared author
W_SIM, W_CAT, W_AUTH = 0.65, 0.25, 0.10
LINK_THRESHOLD = 0.42
LINK_THRESHOLD_TINY = 0.35  # graphs of one or two papers
MAX_EDGES_PER_NODE = 3


def _surname(name: str) -> str:
    parts = (name or "").split()
    return parts[-1] if parts else ""


def build_nodes(papers: Sequence[Any]) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []
    for i, p in enumerate(papers):
        year_str = p.published[:4] if p.published and len(p.published) >= 4 else "0"
        try:
            year = int(year_str)
        except ValueError:
            year = 0
        first_author = next((_surname(a) for a in (p.authors or []) if _surname(a)), "Unknown")
        # Surnames in author order (not set order), so links are reproducible.
        surnames: List[str] = []
        for a in p.authors or []:
            s = _surname(a)
            if s and s not in surnames:
                surnames.append(s)
        nodes.append({
            "id": i,
            "title": p.title,
            "short_label": f"{first_author} {year}" if year > 0 else first_author,
            "year": year,
            "primary_category": p.categories[0] if p.categories else "",
            "author_surnames": surnames[:5],
            "arxiv_url": p.arxiv_url,
            "pdf_url": p.pdf_url,
            "val": p.relevance_score or 0,
            "degree": 0,
            "cluster": None,
        })
    return nodes


def link_weights(papers: Sequence[Any], nodes: List[Dict[str, Any]], sim: np.ndarray):
    """All pairs (i, j, weight), strongest first."""
    out = []
    for i in range(len(papers)):
        for j in range(i + 1, len(papers)):
            ci, cj = set(papers[i].categories or []), set(papers[j].categories or [])
            cat_jac = len(ci & cj) / max(len(ci | cj), 1) if ci and cj else 0.0
            shared = 1.0 if set(nodes[i]["author_surnames"]) & set(nodes[j]["author_surnames"]) else 0.0
            out.append((i, j, W_SIM * float(sim[i][j]) + W_CAT * cat_jac + W_AUTH * shared))
    out.sort(key=lambda x: x[2], reverse=True)
    return out


def build_links(papers: Sequence[Any], nodes: List[Dict[str, Any]], sim: np.ndarray) -> List[Dict[str, Any]]:
    """Keep the strongest pairs above the threshold, at most MAX_EDGES_PER_NODE * n."""
    candidates = link_weights(papers, nodes, sim)
    threshold = LINK_THRESHOLD_TINY if len(papers) <= 2 else LINK_THRESHOLD
    max_edges = len(papers) * MAX_EDGES_PER_NODE
    links: List[Dict[str, Any]] = []
    for i, j, w in candidates:
        if w >= threshold and len(links) < max_edges:
            links.append({"source": i, "target": j, "weight": w})
            nodes[i]["degree"] += 1
            nodes[j]["degree"] += 1
    max_deg = max((n["degree"] for n in nodes), default=1) or 1
    for n in nodes:
        n["val"] = 0.55 * (n["degree"] / max_deg) + 0.45 * n["val"]
    return links


def cluster(n: int, links: List[Dict[str, Any]], method: str = "components",
            resolution: float = 1.0) -> Dict[int, List[int]]:
    """Group node indices. 'components': connected components of the link graph.
    'modularity': greedy modularity communities on the weighted graph
    (Clauset-Newman-Moore, networkx; resolution 1.0 is the standard modularity,
    higher values give more, smaller groups), which splits long chains of links."""
    if method == "modularity" and links:
        import networkx as nx

        g = nx.Graph()
        g.add_nodes_from(range(n))
        g.add_weighted_edges_from((l["source"], l["target"], l["weight"]) for l in links)
        comms = nx.algorithms.community.greedy_modularity_communities(g, weight="weight", resolution=resolution)
        groups = sorted((sorted(c) for c in comms), key=lambda c: (-len(c), c[0]))
        return {cid: members for cid, members in enumerate(groups)}

    adj: Dict[int, List[int]] = {i: [] for i in range(n)}
    for l in links:
        adj[l["source"]].append(l["target"])
        adj[l["target"]].append(l["source"])
    seen: set = set()
    clusters: Dict[int, List[int]] = {}
    for i in range(n):
        if i in seen:
            continue
        comp, stack = [], [i]
        while stack:
            v = stack.pop()
            if v in seen:
                continue
            seen.add(v)
            comp.append(v)
            stack.extend(adj[v])
        clusters[len(clusters)] = sorted(comp)
    return clusters

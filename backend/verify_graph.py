
import numpy as np
from sentence_transformers import SentenceTransformer, util
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class MockPaper:
    title: str
    abstract: str
    relevance_score: Optional[float] = None

def generate_graph(top_papers: List[MockPaper]):
    nodes = []
    for i, p in enumerate(top_papers):
        nodes.append({"id": i, "title": p.title, "val": p.relevance_score or 0})

    links = []
    abstracts = [p.abstract for p in top_papers]
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embs = model.encode(abstracts, convert_to_tensor=True)
    sim_matrix = util.cos_sim(embs, embs)

    print("Similarity Matrix:")
    print(sim_matrix)

    for i in range(len(top_papers)):
        for j in range(i + 1, len(top_papers)):
            sim = float(sim_matrix[i][j])
            if sim > 0.7:
                links.append({"source": i, "target": j, "weight": sim})
    
    return nodes, links

def test():
    papers = [
        MockPaper("AI in Health", "This paper discusses the use of artificial intelligence in healthcare diagnostics.", 0.9),
        MockPaper("ML for Medicine", "Machine learning techniques are applied to improve medical imaging and patient care.", 0.8),
        MockPaper("Cooking Pasta", "A comprehensive guide to boiling the perfect al dente pasta.", 0.1),
    ]
    
    nodes, links = generate_graph(papers)
    print(f"Nodes count: {len(nodes)}")
    print(f"Links count: {len(links)}")

if __name__ == "__main__":
    test()

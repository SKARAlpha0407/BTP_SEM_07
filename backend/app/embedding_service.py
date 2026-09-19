
from sentence_transformers import SentenceTransformer, util
import numpy as np
from typing import List

# Load model once
model = SentenceTransformer('all-MiniLM-L6-v2')

def embed_text(text: str):
    return model.encode(text, convert_to_tensor=True)

def rank_papers(query: str, papers: List):
    if not papers:
        return []
    
    query_emb = embed_text(query)
    # Embed abstracts
    abstracts = [p.abstract for p in papers]
    paper_embs = model.encode(abstracts, convert_to_tensor=True)
    
    # Compute cosine similarities
    scores = util.cos_sim(query_emb, paper_embs)[0]
    
    for i, paper in enumerate(papers):
        paper.relevance_score = float(scores[i])
        
    # Sort by score descending
    return sorted(papers, key=lambda x: x.relevance_score or 0, reverse=True)

"""Synthetic corpus for tests (not real papers)."""

TOPICS = {
    "graph neural networks": "message passing over nodes and edges aggregates neighbourhood features for molecules",
    "speech recognition": "acoustic models transcribe spoken audio waveforms into text with connectionist decoding",
    "image segmentation": "pixel wise masks delineate object boundaries in medical scans using convolutional encoders",
    "machine translation": "sequence models convert sentences between languages with attention over source tokens",
    "reinforcement learning": "agents maximise cumulative reward through exploration of environments and policy gradients",
    "federated learning": "clients train locally and share updates so private records never leave devices",
    "recommender systems": "collaborative filtering predicts user ratings from interaction histories and item factors",
    "quantum computing": "qubits and entangling gates implement circuits that are simulated with error mitigation",
}
ANGLES = ["survey", "benchmark", "efficient training", "robustness analysis", "theory"]


def corpus():
    rows = []
    for t, (topic, body) in enumerate(TOPICS.items()):
        for a, angle in enumerate(ANGLES):
            rows.append({
                "arxiv_id": f"toy.{t:02d}{a:02d}",
                "title": f"A {angle} of {topic}",
                "abstract": f"We study {topic}. This {angle} shows how {body}. "
                            f"Experiments on {topic} confirm the {angle} findings.",
                "categories": [f"cs.T{t}"],
                "primary_category": f"cs.T{t}",
                "published": "2026-01-01",
            })
    return rows

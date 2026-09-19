export interface Paper {
  title: string;
  authors: string[];
  abstract: string;
  arxiv_id: string;
  arxiv_url: string;
  pdf_url: string;
  published: string;
  categories: string[];
  relevance_score: number | null;
  summary: {
    tldr: string;
    problem: string;
    methods: string;
    benchmarks: string;
  } | null;
}

export interface SearchResponse {
  papers: Paper[];
  synthesis: string;
  graph: {
    nodes: Array<{ id: number; title: string; val: number; cluster?: string }>;
    links: Array<{ source: number; target: number; weight: number }>;
  };
}

export const API_BASE = 'http://localhost:8000';

export async function searchResearch(
  topic: string,
  maxResults: number = 5
): Promise<SearchResponse> {
  const response = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, max_results: maxResults }),
  });

  // Backend returns 404 when arXiv has no matches for the topic.
  // Surface that as an empty result, not an error.
  if (response.status === 404) {
    return {
      papers: [],
      synthesis: 'No papers found for this topic.',
      graph: { nodes: [], links: [] },
    };
  }

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Backend search failed (${response.status}): ${detail.slice(0, 200)}`);
  }

  return (await response.json()) as SearchResponse;
}
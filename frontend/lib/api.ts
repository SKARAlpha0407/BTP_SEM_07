
export interface Paper {
  title: string;
  authors: string[];
  abstract: string;
  arxiv_id: string;
  arxiv_url: string;
  pdf_url: string;
  published: string;
  categories: string[];
  relevance_score: number;
  summary: {
    tl_dr: string;
    problem: string;
    methods: string;
    benchmarks: Array<{ dataset: string; metric: string; result: string; baseline: string }>;
  };
}

export interface SearchResponse {
  papers: Paper[];
  synthesis: string;
  graph: {
    nodes: Array<{ id: number; title: string; val: number }>;
    links: Array<{ source: number; target: number; weight: number }>;
  };
}

export async function searchResearch(topic: string): Promise<SearchResponse> {
  const response = await fetch('http://localhost:8000/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic }),
  });
  if (!response.ok) throw new Error('Backend search failed');
  return response.json();
}

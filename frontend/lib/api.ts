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
    grounding?: { score: number; unsupported: string[] };
  } | null;
  matched_terms?: string[];
}

export interface SearchResponse {
  papers: Paper[];
  synthesis: string;
  graph: {
    nodes: Array<{ id: number; title: string; val: number; cluster?: string }>;
    links: Array<{ source: number; target: number; weight: number }>;
  };
  meta?: {
    cache_path: 'warm' | 'cold';
    latency_seconds: number;
    embed_model: string;
    hybrid_retrieval: boolean;
  };
}

// Where the FastAPI backend lives, in order of preference:
// 1. A tunnel URL this device has accepted from a share link
//    (`?api=https://<name>.trycloudflare.com`, see ./tunnel.sh). A link never
//    switches the backend by itself: anyone can create a trycloudflare.com
//    address, so the page asks first (pendingLinkBackend / acceptBackend).
// 2. NEXT_PUBLIC_API_BASE, set in the deployment and read at build time.
// 3. A backend on the same machine (development).
const BUILD_API_BASE = (process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000').replace(/\/$/, '');
const STORAGE_KEY = 'kavosh-api-base';

// Only tunnel or local addresses are accepted from a link, so a crafted link
// cannot send a visitor's searches to an arbitrary server.
function isAllowedOverride(url: string) {
  try {
    const u = new URL(url);
    return (
      (u.protocol === 'https:' && /\.trycloudflare\.com$/.test(u.hostname)) ||
      (/^(localhost|127\.0\.0\.1)$/.test(u.hostname) && (u.protocol === 'http:' || u.protocol === 'https:'))
    );
  } catch {
    return false;
  }
}

function savedBackend(): string | null {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return saved && isAllowedOverride(saved) ? saved : null;
  } catch {
    return null; // storage blocked (private mode)
  }
}

export function getApiBase(): string {
  if (typeof window === 'undefined') return BUILD_API_BASE;
  return savedBackend() ?? BUILD_API_BASE;
}

/** A backend named in the page link that this device has not accepted yet. */
export function pendingLinkBackend(): string | null {
  if (typeof window === 'undefined') return null;
  const fromLink = new URLSearchParams(window.location.search).get('api');
  if (!fromLink) return null;
  const clean = fromLink.replace(/\/$/, '');
  if (!isAllowedOverride(clean) || clean === getApiBase()) {
    clearLinkParam();
    return null;
  }
  return clean;
}

/** Use (or decline) the backend from the link, then tidy the address bar. */
export function acceptBackend(url: string | null) {
  if (url && isAllowedOverride(url)) {
    try {
      window.localStorage.setItem(STORAGE_KEY, url);
    } catch {
      // Without storage the choice lasts only until reload.
    }
  }
  clearLinkParam();
}

function clearLinkParam() {
  const u = new URL(window.location.href);
  if (!u.searchParams.has('api')) return;
  u.searchParams.delete('api');
  window.history.replaceState(null, '', u.pathname + u.search + u.hash);
}

/**
 * Paper links come from the backend; only open them if they point at arXiv,
 * so a rogue backend cannot turn "PDF" into a link to anywhere.
 */
export function safeArxivUrl(url?: string | null): string | undefined {
  if (!url) return undefined;
  try {
    const u = new URL(url.replace(/^http:\/\//, 'https://'));
    return u.protocol === 'https:' && /(^|\.)arxiv\.org$/.test(u.hostname) ? u.toString() : undefined;
  } catch {
    return undefined;
  }
}

const isLocalUrl = (url: string) => /^https?:\/\/(localhost|127\.0\.0\.1)(:|\/|$)/.test(url);

export function backendHint(): { short: string; long: string } {
  const pageIsLocal =
    typeof window === 'undefined' || /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname);
  const apiIsLocal = isLocalUrl(getApiBase());
  if (apiIsLocal && pageIsLocal) {
    return {
      short: 'Backend not reachable at localhost:8000 · run ./dev.sh',
      long: 'Check that the backend is running on port 8000 (./dev.sh starts it), then search again.',
    };
  }
  if (apiIsLocal) {
    return {
      short: 'Search is not connected on this site',
      long: 'This site has no search backend connected. Open it with the link from ./tunnel.sh (it ends in ?api=…).',
    };
  }
  return {
    short: 'Search service is offline · try again later',
    long: 'The search service did not respond. It may be starting up; try again in a minute.',
  };
}

export async function searchResearch(
  topic: string,
  maxResults: number = 5
): Promise<SearchResponse> {
  const response = await fetch(`${getApiBase()}/search`, {
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
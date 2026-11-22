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
    grounding?: { score: number | null; unsupported: string[] };
  } | null;
  matched_terms?: string[];
}

export interface SearchResponse {
  papers: Paper[];
  synthesis: string;
  graph: {
    nodes: Array<{
      id: number;
      title: string;
      val: number;
      cluster?: string;
      year?: number;
      short_label?: string;
      primary_category?: string;
      degree?: number;
      author_surnames?: string[];
      arxiv_url?: string;
      pdf_url?: string;
    }>;
    links: Array<{ source: number; target: number; weight: number }>;
  };
  meta?: SearchMeta;
}

// warm: served from the semantic cache; cold: fetched from arXiv now;
// stale: arXiv was unavailable, so papers stored earlier are shown.
export type CachePath = 'warm' | 'cold' | 'stale';

export interface SearchMeta {
  cache_path: CachePath;
  latency_seconds: number;
  embed_model: string;
  hybrid_retrieval: boolean;
}

// Where the FastAPI backend lives, in order of preference:
// 1. A tunnel URL given in the page link, `?api=https://<name>.trycloudflare.com`
//    (see ./tunnel.sh). It is remembered on this device for OVERRIDE_TTL_MS, is
//    dropped when its /health check fails, and can be reset from the status bar.
// 2. NEXT_PUBLIC_API_BASE, set in the deployment and read at build time.
// 3. A backend on the same machine (development).
const BUILD_API_BASE = (process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000').replace(/\/$/, '');
const STORAGE_KEY = 'kavosh-api-base';
const OVERRIDE_TTL_MS = 24 * 60 * 60 * 1000;

// A link may only point at a bare tunnel or local origin (no path, query or
// credentials). Anyone can create a trycloudflare host, so the override is
// short-lived, visible in the status bar, and removable.
function cleanOverride(raw: string): string | null {
  try {
    const u = new URL(raw);
    if (u.username || u.password || u.search || u.hash || (u.pathname && u.pathname !== '/')) return null;
    const tunnel = u.protocol === 'https:' && /^[a-z0-9-]+\.trycloudflare\.com$/.test(u.hostname);
    const local = /^(localhost|127\.0\.0\.1)$/.test(u.hostname) && (u.protocol === 'http:' || u.protocol === 'https:');
    return tunnel || local ? u.origin : null;
  } catch {
    return null;
  }
}

function readSavedOverride(): string | null {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const { url, at } = JSON.parse(raw) as { url: string; at: number };
    const clean = cleanOverride(url);
    if (clean && typeof at === 'number' && Date.now() - at < OVERRIDE_TTL_MS) return clean;
  } catch {
    // Old format (a bare URL) or corrupt: drop it.
  }
  window.localStorage.removeItem(STORAGE_KEY);
  return null;
}

export function getApiBase(): string {
  if (typeof window === 'undefined') return BUILD_API_BASE;
  try {
    const fromLink = new URLSearchParams(window.location.search).get('api');
    const clean = fromLink ? cleanOverride(fromLink) : null;
    if (clean) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ url: clean, at: Date.now() }));
      return clean;
    }
    const saved = readSavedOverride();
    if (saved) return saved;
  } catch {
    // Storage blocked (private mode): fall through to the build setting.
  }
  return BUILD_API_BASE;
}

/** Host of the backend chosen by a link, or null when the default is in use. */
export function apiOverrideHost(): string | null {
  const base = getApiBase();
  if (base === BUILD_API_BASE) return null;
  try {
    return new URL(base).host;
  } catch {
    return null;
  }
}

/** Forget a backend chosen by a link and drop ?api= from the address bar. */
export function clearApiOverride(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
  const url = new URL(window.location.href);
  if (url.searchParams.has('api')) {
    url.searchParams.delete('api');
    window.history.replaceState(null, '', url.toString());
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

export type SearchErrorKind = 'network' | 'timeout' | 'invalid' | 'rate' | 'busy' | 'server';

export class SearchError extends Error {
  constructor(public kind: SearchErrorKind, message: string, public retryAfter?: number) {
    super(message);
    this.name = 'SearchError';
  }
}

const EMPTY: SearchResponse = { papers: [], synthesis: '', graph: { nodes: [], links: [] } };

async function readDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return typeof body?.detail === 'string' ? body.detail : '';
  } catch {
    return '';
  }
}

function retrySeconds(res: Response): number | undefined {
  const v = Number(res.headers.get('Retry-After'));
  return Number.isFinite(v) && v > 0 ? v : undefined;
}

const wait = (s?: number) => (s ? ` Try again in about ${s} seconds.` : ' Try again shortly.');

/**
 * POST /search. Resolves with results (an empty list when arXiv found nothing)
 * or rejects with a SearchError whose message is fit to show to a reader.
 */
export async function searchResearch(
  topic: string,
  maxResults: number = 5,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  let res: Response;
  try {
    res = await fetch(`${getApiBase()}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, max_results: maxResults }),
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw new SearchError('network', 'The search service could not be reached.');
  }

  if (res.ok) return (await res.json()) as SearchResponse;

  const detail = await readDetail(res);
  if (res.status === 404 && detail.startsWith('No papers matched')) return EMPTY;
  if (res.status === 422) throw new SearchError('invalid', 'That topic could not be searched. Use 1 to 500 characters.');
  if (res.status === 429) {
    const s = retrySeconds(res);
    throw new SearchError('rate', `Too many searches right now.${wait(s)}`, s);
  }
  if (res.status === 503) {
    const s = retrySeconds(res);
    throw new SearchError('busy', `arXiv is busy and no stored papers match this topic.${wait(s)}`, s);
  }
  throw new SearchError('server', `The search failed on the server (error ${res.status}). Try again.`);
}

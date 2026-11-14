import React, { useState } from 'react';
import Head from 'next/head';
import {
  AlertTriangle,
  ArrowRight,
  ExternalLink,
  FileText,
  Network,
  Search,
  SearchX,
  Sparkles,
} from 'lucide-react';
import { Paper, SearchResponse } from '../lib/api';
import dynamic from 'next/dynamic';
const ReadingMap = dynamic(() => import('../components/ReadingMap'), { ssr: false });

type BenchmarkRow = {
  dataset: string;
  metric: string;
  result: string;
  baseline: string;
};

const API_BASE = 'http://localhost:8000';

const SUGGESTIONS = ['Transformers', 'RAG', 'Diffusion Models', 'Graph Neural Networks'];
const PIPELINE_STEPS = ['Query', 'Search', 'Rank', 'Extract', 'Synthesize'];

export default function Home() {
  const [topic, setTopic] = useState('');
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(-1);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Which panel fills the bottom of the results area
  const [bottomTab, setBottomTab] = useState<'synthesis' | 'paper'>('synthesis');

  // `override` lets a suggestion chip search without waiting for setTopic.
  const handleSearch = async (e?: React.FormEvent, override?: string) => {
    e?.preventDefault();
    const trimmed = (override ?? topic).trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);
    setResults(null);
    setSelectedPaper(null);
    setBottomTab('synthesis');

    try {
      // Simulated pipeline progress for UI feel — real work happens in the fetch below.
      for (let i = 0; i < 5; i++) {
        setStep(i);
        await new Promise((r) => setTimeout(r, 400));
      }

      const res = await fetch(`${API_BASE}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: trimmed, max_results: 5 }),
      });

      // Backend returns 404 when arXiv has no matches for the topic.
      // Treat that as a valid empty result, not an error.
      if (res.status === 404) {
        setResults({
          papers: [],
          synthesis: 'No papers found for this topic.',
          graph: { nodes: [], links: [] },
        } as SearchResponse);
        return;
      }

      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`Backend returned ${res.status}: ${detail.slice(0, 200)}`);
      }

      const data: SearchResponse = await res.json();
      setResults(data);
      if (data.papers.length > 0) {
        setSelectedPaper(data.papers[0]);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Search failed. Ensure backend is running on port 8000.'
      );
    } finally {
      setLoading(false);
      setStep(-1);
    }
  };

  const runSuggestion = (q: string) => {
    setTopic(q);
    handleSearch(undefined, q);
  };

  const selectPaper = (p: Paper) => {
    setSelectedPaper(p);
    setBottomTab('paper');
  };

  const isLanding = !loading && !results && !error;

  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100 font-sans antialiased selection:bg-indigo-500/30">
      <Head>
        <title>Research Copilot — arXiv Search</title>
      </Head>

      {isLanding ? (
        <Landing
          topic={topic}
          setTopic={setTopic}
          onSubmit={handleSearch}
          onSuggestion={runSuggestion}
        />
      ) : (
        <>
          <Navbar
            topic={topic}
            setTopic={setTopic}
            onSubmit={handleSearch}
            loading={loading}
            meta={results?.meta}
          />

          {error && (
            <div className="mx-auto max-w-3xl px-4 pt-6">
              <div className="flex items-start gap-3 rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-300">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span className="break-words">{error}</span>
              </div>
            </div>
          )}

          {loading && <LoadingView step={step} />}

          {!loading && results && results.papers.length === 0 && (
            <div className="flex flex-col items-center justify-center px-4 py-32 text-center">
              <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-900">
                <SearchX className="h-6 w-6 text-zinc-500" />
              </div>
              <h2 className="mb-2 text-xl font-semibold">No papers found</h2>
              <p className="max-w-md text-sm text-zinc-400">
                arXiv had no matches for &ldquo;{topic}&rdquo;. Try a broader term or a different
                phrasing.
              </p>
            </div>
          )}

          {!loading && results && results.papers.length > 0 && (
            <div className="flex flex-col lg:h-[calc(100vh-57px)] lg:flex-row">
              {/* Ranked papers */}
              <aside className="border-zinc-800 lg:w-[30%] lg:min-w-[300px] lg:overflow-y-auto lg:border-r">
                <div className="sticky top-0 z-10 flex items-center justify-between border-b border-zinc-800 bg-[#09090b]/90 px-4 py-3 backdrop-blur-md">
                  <h3 className="text-[11px] font-semibold uppercase tracking-widest text-zinc-500">
                    Ranked papers
                  </h3>
                  <span className="text-[11px] tabular-nums text-zinc-500">
                    {results.papers.length} results
                  </span>
                </div>
                <ol className="space-y-2 p-3">
                  {results.papers.map((p, i) => (
                    <li key={p.arxiv_id}>
                      <PaperCard
                        paper={p}
                        rank={i + 1}
                        active={selectedPaper?.arxiv_id === p.arxiv_id}
                        onClick={() => selectPaper(p)}
                      />
                    </li>
                  ))}
                </ol>
              </aside>

              {/* Graph + synthesis */}
              <main className="flex min-w-0 flex-1 flex-col">
                <section className="relative h-[420px] border-b border-zinc-800 bg-[radial-gradient(ellipse_at_center,rgba(99,102,241,0.08),transparent_70%)] lg:h-1/2">
                  <ReadingMap data={results.graph} />
                </section>

                <section className="flex min-h-0 flex-1 flex-col">
                  <div className="flex items-center gap-1 border-b border-zinc-800 px-4">
                    <TabButton
                      active={bottomTab === 'synthesis'}
                      onClick={() => setBottomTab('synthesis')}
                      icon={<Sparkles className="h-3.5 w-3.5" />}
                      label="Cross-paper synthesis"
                    />
                    <TabButton
                      active={bottomTab === 'paper'}
                      onClick={() => setBottomTab('paper')}
                      icon={<FileText className="h-3.5 w-3.5" />}
                      label="Selected paper"
                      disabled={!selectedPaper}
                    />
                  </div>

                  <div className="flex-1 overflow-y-auto px-6 py-6">
                    {bottomTab === 'synthesis' ? (
                      <div className="max-w-3xl">
                        <p className="text-[15px] leading-relaxed text-zinc-300 whitespace-pre-wrap">
                          {results.synthesis}
                        </p>
                      </div>
                    ) : selectedPaper ? (
                      <PaperDetails paper={selectedPaper} />
                    ) : null}
                  </div>
                </section>
              </main>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Landing
// ---------------------------------------------------------------------------

function Landing({
  topic,
  setTopic,
  onSubmit,
  onSuggestion,
}: {
  topic: string;
  setTopic: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onSuggestion: (q: string) => void;
}) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-4">
      {/* Ambient glow and grid */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-1/3 h-[480px] w-[720px] max-w-[140vw] -translate-x-1/2 -translate-y-1/2 rounded-full bg-indigo-600/20 blur-[120px]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:64px_64px] [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]"
      />

      <div className="relative z-10 flex w-full max-w-2xl flex-col items-center text-center">
        <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-xs font-medium text-indigo-300">
          <Network className="h-3.5 w-3.5" />
          Research Copilot
        </div>

        <h1 className="bg-gradient-to-b from-white via-zinc-200 to-zinc-500 bg-clip-text pb-2 text-4xl font-semibold tracking-tight text-transparent sm:text-6xl">
          Discover the frontier
          <br />
          of{' '}
          <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-fuchsia-400 bg-clip-text text-transparent">
            AI research.
          </span>
        </h1>
        <p className="mt-4 text-base text-zinc-400 sm:text-lg">
          Enter a topic to map the landscape of academic papers.
        </p>

        <form onSubmit={onSubmit} className="mt-10 w-full">
          <div className="group relative flex items-center rounded-full border border-zinc-800 bg-zinc-900 shadow-2xl shadow-indigo-950/40 transition-colors focus-within:border-indigo-500/50 focus-within:ring-2 focus-within:ring-indigo-500/50">
            <Search className="pointer-events-none absolute left-5 h-5 w-5 text-zinc-500 transition-colors group-focus-within:text-indigo-400" />
            <input
              autoFocus
              className="w-full rounded-full bg-transparent py-4 pl-14 pr-16 text-base text-zinc-100 placeholder:text-zinc-500 outline-none"
              placeholder="Search a research topic, e.g. retrieval-augmented generation"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              aria-label="Research topic"
            />
            <button
              type="submit"
              disabled={!topic.trim()}
              aria-label="Search"
              className="absolute right-2 flex h-10 w-10 items-center justify-center rounded-full bg-indigo-500 text-white transition-all hover:bg-indigo-400 disabled:bg-zinc-800 disabled:text-zinc-500"
            >
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </form>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          <span className="mr-1 text-xs text-zinc-500">Try</span>
          {SUGGESTIONS.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => onSuggestion(q)}
              className="rounded-full border border-zinc-800 bg-zinc-900/60 px-3.5 py-1.5 text-xs text-zinc-300 transition-colors hover:border-indigo-500/40 hover:bg-indigo-500/10 hover:text-indigo-300"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Navbar (results and loading)
// ---------------------------------------------------------------------------

function Navbar({
  topic,
  setTopic,
  onSubmit,
  loading,
  meta,
}: {
  topic: string;
  setTopic: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  loading: boolean;
  meta?: SearchResponse['meta'];
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-zinc-800 bg-[#09090b]/80 backdrop-blur-md">
      <div className="flex h-14 items-center gap-4 px-4">
        <div className="flex shrink-0 items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/20">
            <Network className="h-4 w-4 text-white" />
          </div>
          <span className="hidden text-sm font-semibold tracking-tight sm:inline">Research Copilot</span>
        </div>

        <form onSubmit={onSubmit} className="mx-auto w-full max-w-xl">
          <div className="group relative flex items-center rounded-full border border-zinc-800 bg-zinc-900 transition-colors focus-within:border-indigo-500/50 focus-within:ring-2 focus-within:ring-indigo-500/50">
            <Search className="pointer-events-none absolute left-3.5 h-4 w-4 text-zinc-500 group-focus-within:text-indigo-400" />
            <input
              className="w-full rounded-full bg-transparent py-1.5 pl-10 pr-24 text-sm text-zinc-100 placeholder:text-zinc-500 outline-none disabled:opacity-60"
              placeholder="Search another topic…"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              disabled={loading}
              aria-label="Research topic"
            />
            <button
              type="submit"
              disabled={loading || !topic.trim()}
              className="absolute right-1 rounded-full bg-indigo-500 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-indigo-400 disabled:bg-zinc-800 disabled:text-zinc-500"
            >
              {loading ? 'Searching…' : 'Search'}
            </button>
          </div>
        </form>

        <div className="hidden shrink-0 items-center gap-2 md:flex">
          {meta && (
            <>
              <span
                className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                  meta.cache_path === 'warm'
                    ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300'
                    : 'border-zinc-700 bg-zinc-800/60 text-zinc-400'
                }`}
                title={meta.cache_path === 'warm' ? 'Served from the semantic cache' : 'Fetched live from arXiv'}
              >
                {meta.cache_path === 'warm' ? 'Cached' : 'Live'}
              </span>
              <span className="text-[11px] tabular-nums text-zinc-500">
                {meta.latency_seconds.toFixed(1)}s
              </span>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------
// Loading
// ---------------------------------------------------------------------------

function LoadingView({ step }: { step: number }) {
  return (
    <div className="flex flex-col lg:h-[calc(100vh-57px)] lg:flex-row" aria-busy="true">
      <aside className="border-zinc-800 lg:w-[30%] lg:min-w-[300px] lg:border-r">
        <div className="border-b border-zinc-800 px-4 py-3">
          <div className="h-3 w-28 animate-pulse rounded bg-zinc-800" />
        </div>
        <div className="space-y-2 p-3">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
              <div className="mb-3 flex items-center justify-between">
                <div className="h-3 w-6 animate-pulse rounded bg-zinc-800" />
                <div className="h-4 w-12 animate-pulse rounded-full bg-zinc-800" />
              </div>
              <div className="mb-2 h-3.5 w-full animate-pulse rounded bg-zinc-800" />
              <div className="mb-4 h-3.5 w-3/4 animate-pulse rounded bg-zinc-800" />
              <div className="h-1 w-full animate-pulse rounded-full bg-zinc-800" />
            </div>
          ))}
        </div>
      </aside>

      <main className="relative flex flex-1 items-center justify-center p-4">
        <div className="relative flex h-[420px] w-full animate-pulse items-center justify-center overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/60 lg:h-full">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(99,102,241,0.12),transparent_65%)]" />
        </div>
        {/* Kept outside the pulsing box so the text stays steady */}
        <div className="pointer-events-none absolute flex flex-col items-center gap-5 text-center">
          <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
            <Network className="h-4 w-4 text-indigo-400" />
            Mapping the research landscape...
          </div>
          <ol className="flex items-center gap-2">
            {PIPELINE_STEPS.map((s, i) => (
              <li key={s} className="flex items-center gap-2">
                <span
                  className={`rounded-full border px-2.5 py-0.5 text-[11px] transition-colors ${
                    i < step
                      ? 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300'
                      : i === step
                        ? 'border-indigo-400/60 bg-indigo-500/20 text-indigo-200'
                        : 'border-zinc-800 text-zinc-600'
                  }`}
                >
                  {s}
                </span>
                {i < PIPELINE_STEPS.length - 1 && <span className="h-px w-3 bg-zinc-800" />}
              </li>
            ))}
          </ol>
        </div>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Results pieces
// ---------------------------------------------------------------------------

function PaperCard({
  paper,
  rank,
  active,
  onClick,
}: {
  paper: Paper;
  rank: number;
  active: boolean;
  onClick: () => void;
}) {
  const pct = Math.max(0, Math.min(100, (paper.relevance_score ?? 0) * 100));
  return (
    <button
      type="button"
      onClick={onClick}
      className={`group w-full rounded-xl border p-4 text-left transition-all ${
        active
          ? 'border-indigo-500/40 bg-indigo-500/10 shadow-lg shadow-indigo-950/30'
          : 'border-zinc-800 bg-zinc-900/50 hover:border-zinc-700 hover:bg-zinc-900'
      }`}
    >
      <div className="mb-2 flex items-center justify-between">
        <span
          className={`font-mono text-xs tabular-nums ${active ? 'text-indigo-300' : 'text-zinc-500'}`}
        >
          {String(rank).padStart(2, '0')}
        </span>
        <span
          className={`rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums ${
            active ? 'bg-indigo-500/20 text-indigo-200' : 'bg-zinc-800 text-zinc-300'
          }`}
        >
          {pct.toFixed(1)}%
        </span>
      </div>
      <h4
        className={`mb-3 text-sm font-medium leading-snug ${
          active ? 'text-zinc-50' : 'text-zinc-200 group-hover:text-zinc-50'
        }`}
      >
        {paper.title}
      </h4>
      {(paper.matched_terms?.length ?? 0) > 0 && (
        <div className="mb-3 flex flex-wrap gap-1" title="Query terms found in this paper">
          {paper.matched_terms!.map((t) => (
            <span
              key={t}
              className="rounded border border-zinc-800 bg-zinc-950/60 px-1.5 py-0.5 text-[10px] text-zinc-400"
            >
              {t}
            </span>
          ))}
        </div>
      )}
      <div className="h-1 w-full overflow-hidden rounded-full bg-zinc-800">
        <div
          className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-400"
          style={{ width: `${pct}%` }}
        />
      </div>
    </button>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
  disabled,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`-mb-px flex items-center gap-1.5 border-b-2 px-3 py-3 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
        active
          ? 'border-indigo-400 text-zinc-100'
          : 'border-transparent text-zinc-500 hover:text-zinc-300'
      }`}
    >
      <span className={active ? 'text-indigo-400' : ''}>{icon}</span>
      {label}
    </button>
  );
}

function PaperDetails({ paper }: { paper: Paper }) {
  return (
    <div className="max-w-3xl space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-xl font-semibold leading-snug text-zinc-50">{paper.title}</h2>
          <p className="mt-1.5 text-sm text-zinc-400">
            {paper.authors.join(', ')} · {paper.published}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <a
            href={paper.arxiv_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-800 px-3 py-1.5 text-xs text-zinc-300 transition-colors hover:border-zinc-700 hover:bg-zinc-900"
          >
            arXiv <ExternalLink className="h-3 w-3" />
          </a>
          <a
            href={paper.pdf_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-100 px-3 py-1.5 text-xs font-medium text-zinc-900 transition-colors hover:bg-white"
          >
            PDF <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>

      <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-4">
        <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-indigo-400">TL;DR</h4>
        <p className="leading-relaxed text-zinc-200">{paper.summary?.tldr ?? '—'}</p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <InsightBlock title="Problem" body={paper.summary?.problem} />
        <InsightBlock title="Methods" body={paper.summary?.methods} />
      </div>

      <BenchmarksPanel benchmarks={paper.summary?.benchmarks} />

      {(paper.summary?.grounding?.unsupported?.length ?? 0) > 0 && (
        <p className="flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-300">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Check against the abstract — these terms in the AI summary do not appear in it:{' '}
            {paper.summary!.grounding!.unsupported.join(', ')}
          </span>
        </p>
      )}
    </div>
  );
}

function InsightBlock({ title, body }: { title: string; body?: string }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
      <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-zinc-500">{title}</h4>
      <p className="text-sm leading-relaxed text-zinc-300">{body ?? '—'}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// BenchmarksPanel — accepts either a string (what the current backend prompt
// produces) or an array of {dataset, metric, result, baseline} rows.
// ---------------------------------------------------------------------------

function BenchmarksPanel({ benchmarks }: { benchmarks: any }) {
  if (!benchmarks) return null;

  if (typeof benchmarks === 'string') {
    if (!benchmarks.trim() || benchmarks.trim().toUpperCase() === 'N/A') return null;
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
        <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-zinc-500">Benchmarks</h4>
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-300">{benchmarks}</p>
      </div>
    );
  }

  if (Array.isArray(benchmarks) && benchmarks.length > 0) {
    const rows = benchmarks as BenchmarkRow[];
    return (
      <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
        <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-zinc-500">Benchmarks</h4>
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-500">
              <th className="pb-2 font-medium">Dataset</th>
              <th className="pb-2 font-medium">Metric</th>
              <th className="pb-2 font-medium">Result</th>
              <th className="pb-2 font-medium">Baseline</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((b, i) => (
              <tr key={i} className="border-b border-zinc-800/60 last:border-0">
                <td className="py-2 font-medium text-zinc-200">{b.dataset}</td>
                <td className="py-2 text-zinc-400">{b.metric}</td>
                <td className="py-2 font-semibold tabular-nums text-indigo-300">{b.result}</td>
                <td className="py-2 tabular-nums text-zinc-500">{b.baseline}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return null;
}

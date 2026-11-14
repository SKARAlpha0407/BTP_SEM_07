import React, { useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import dynamic from 'next/dynamic';
import { AlertTriangle, ArrowUpRight, Check, Info, Search } from 'lucide-react';
import { Paper, SearchResponse } from '../lib/api';

/*
 * Design rules: .claude/skills/research-copilot-ui/SKILL.md
 * Tokens (bg-page, text-ink, border-line, ...) live in styles/globals.css.
 */

const ReadingMap = dynamic(() => import('../components/ReadingMap'), { ssr: false });

type BenchmarkRow = {
  dataset: string;
  metric: string;
  result: string;
  baseline: string;
};

type Health = { status: string; embed_model?: string; llm_model?: string; hybrid_retrieval?: boolean };

const API_BASE = 'http://localhost:8000';

const EXAMPLES = [
  'retrieval augmented generation',
  'diffusion models for video',
  'graph neural networks',
  'LLM evaluation',
  'vision transformers',
];

const PIPELINE_STEPS = [
  { name: 'Query', doing: 'Reading your topic' },
  { name: 'Search', doing: 'Searching arXiv' },
  { name: 'Rank', doing: 'Ranking abstracts by meaning' },
  { name: 'Extract', doing: 'Summarising each paper' },
  { name: 'Synthesize', doing: 'Writing the synthesis' },
];

export default function Home() {
  const [topic, setTopic] = useState('');
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(-1);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The topic the current results are for (the input can change after a search).
  const [searched, setSearched] = useState('');
  const [view, setView] = useState<'synthesis' | 'paper'>('synthesis');
  const [health, setHealth] = useState<Health | null | 'offline'>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 3000);
    fetch(`${API_BASE}/health`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((h: Health) => setHealth(h))
      .catch(() => setHealth('offline'))
      .finally(() => clearTimeout(timer));
    return () => ctrl.abort();
  }, []);

  // `override` lets an example search without waiting for setTopic.
  const handleSearch = async (e?: React.FormEvent, override?: string) => {
    e?.preventDefault();
    const trimmed = (override ?? topic).trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);
    setResults(null);
    setSelectedPaper(null);
    setSearched(trimmed);
    setView('synthesis');

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

  const runExample = (q: string) => {
    setTopic(q);
    handleSearch(undefined, q);
  };

  const openPaper = (p: Paper) => {
    setSelectedPaper(p);
    setView('paper');
  };

  const goHome = () => {
    setResults(null);
    setError(null);
    setSelectedPaper(null);
  };

  const isStart = !loading && !results && !error;

  return (
    <div className="min-h-screen bg-page text-ink">
      <Head>
        <title>Research Copilot</title>
        <meta name="description" content="Find, rank, summarise and map arXiv papers on a research topic." />
      </Head>

      {isStart ? (
        <StartPage
          topic={topic}
          setTopic={setTopic}
          onSubmit={handleSearch}
          onExample={runExample}
          health={health}
        />
      ) : (
        <div className="flex min-h-screen flex-col lg:h-screen">
          <TopBar
            topic={topic}
            setTopic={setTopic}
            onSubmit={handleSearch}
            onHome={goHome}
            loading={loading}
            meta={results?.meta}
          />

          {loading && <LoadingView step={step} topic={searched} />}

          {!loading && error && (
            <StateMessage
              tone="warn"
              title="The search did not finish"
              body={
                <>
                  <span className="font-mono text-[13px]">{error}</span>
                  <br />
                  Check that the backend is running on port 8000 (<code className="font-mono">./dev.sh</code> starts it),
                  then search again.
                </>
              }
              action={
                searched ? (
                  <button
                    type="button"
                    onClick={() => handleSearch(undefined, searched)}
                    className="rounded-sm bg-accent px-3 py-1.5 text-[13px] font-medium text-accent-ink transition-opacity duration-[120ms] hover:opacity-90"
                  >
                    Search again
                  </button>
                ) : null
              }
            />
          )}

          {!loading && !error && results && results.papers.length === 0 && (
            <StateMessage
              title={`No papers found for “${searched}”`}
              body="arXiv returned nothing for this phrase. Try a broader term or fewer words."
            />
          )}

          {!loading && !error && results && results.papers.length > 0 && (
            <ResultsView
              results={results}
              searched={searched}
              selectedPaper={selectedPaper}
              view={view}
              setView={setView}
              onOpenPaper={openPaper}
            />
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Start page
// ---------------------------------------------------------------------------

function StartPage({
  topic,
  setTopic,
  onSubmit,
  onExample,
  health,
}: {
  topic: string;
  setTopic: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onExample: (q: string) => void;
  health: Health | null | 'offline';
}) {
  const embed = health && health !== 'offline' ? health.embed_model : undefined;
  const llm = health && health !== 'offline' ? health.llm_model : undefined;

  return (
    <main className="mx-auto flex w-full max-w-[720px] flex-col gap-10 px-4 pb-16 pt-[12vh] sm:px-6">
      <header className="flex flex-col gap-4">
        <p className="text-[14px] font-semibold tracking-tight text-ink">Research Copilot</p>
        <h1 className="font-serif text-[28px] font-semibold leading-[1.2] text-ink [text-wrap:balance] sm:text-[32px]">
          Find the papers that matter on a topic, and see how they connect.
        </h1>
        <p className="max-w-[60ch] text-[15px] leading-relaxed text-ink-2">
          Type a research topic. Research Copilot pulls matching papers from arXiv, ranks them by meaning,
          summarises each one and maps how they relate.
        </p>
      </header>

      <div className="flex flex-col gap-4">
        <SearchField topic={topic} setTopic={setTopic} onSubmit={onSubmit} size="lg" autoFocus />
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2 text-[13px]">
          <span className="text-muted">Examples</span>
          {EXAMPLES.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => onExample(q)}
              className="rounded-sm text-ink-2 underline decoration-line underline-offset-4 transition-colors duration-[120ms] hover:text-accent hover:decoration-accent"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      <section className="border-t border-line pt-6">
        <h2 className="mb-4 text-[11px] font-medium uppercase tracking-[0.06em] text-muted">What happens when you search</h2>
        <ol className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
          {[
            ['Search arXiv', 'Up to 30 candidate papers that match your topic.'],
            [
              'Rank by meaning',
              `Each abstract is embedded${embed ? ` with ${embed}` : ''} and scored against your topic.`,
            ],
            [
              'Summarise',
              `${llm ? `${llm} writes` : 'A language model writes'} a TL;DR, problem, method and benchmarks for each paper, checked against its abstract.`,
            ],
            ['Map', 'Papers are linked by similarity and grouped into named clusters you can explore.'],
          ].map(([title, body], i) => (
            <li key={title} className="flex gap-3">
              <span className="w-4 shrink-0 font-mono text-[13px] text-muted tabular-nums">{i + 1}</span>
              <div>
                <p className="text-[14px] font-medium text-ink">{title}</p>
                <p className="mt-0.5 text-[13px] leading-relaxed text-ink-2">{body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <p className="flex items-center gap-2 text-[12px] text-muted">
        {health === null && 'Checking the backend…'}
        {health === 'offline' && (
          <>
            <AlertTriangle className="h-3.5 w-3.5 text-warn" aria-hidden />
            <span>
              <span className="text-warn">Backend not reachable</span> at localhost:8000. Start it with{' '}
              <code className="font-mono">./dev.sh</code>.
            </span>
          </>
        )}
        {health && health !== 'offline' && (
          <>
            <Check className="h-3.5 w-3.5 text-accent" aria-hidden />
            <span>
              Backend ready
              {health.hybrid_retrieval ? ' · hybrid retrieval on' : ''}
            </span>
          </>
        )}
      </p>
    </main>
  );
}

function SearchField({
  topic,
  setTopic,
  onSubmit,
  size,
  disabled,
  autoFocus,
}: {
  topic: string;
  setTopic: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  size: 'lg' | 'sm';
  disabled?: boolean;
  autoFocus?: boolean;
}) {
  const lg = size === 'lg';
  return (
    <form onSubmit={onSubmit} role="search" className="w-full">
      <div
        className={`flex items-center rounded-md border border-line bg-surface transition-colors duration-[120ms] focus-within:border-accent ${
          lg ? 'h-12 pl-4 pr-1.5' : 'h-9 pl-3 pr-1'
        }`}
      >
        <Search className={`shrink-0 text-muted ${lg ? 'h-[18px] w-[18px]' : 'h-4 w-4'}`} aria-hidden />
        <input
          id={lg ? 'topic-start' : 'topic-bar'}
          autoFocus={autoFocus}
          className={`min-w-0 flex-1 bg-transparent text-ink outline-none placeholder:text-muted disabled:opacity-60 focus-visible:outline-none ${
            lg ? 'px-3 text-[16px]' : 'px-2 text-[14px]'
          }`}
          placeholder="Research topic, e.g. retrieval augmented generation"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          disabled={disabled}
          aria-label="Research topic"
        />
        <button
          type="submit"
          disabled={disabled || !topic.trim()}
          className={`shrink-0 rounded-sm bg-accent font-medium text-accent-ink transition-opacity duration-[120ms] hover:opacity-90 disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-muted ${
            lg ? 'px-4 py-2 text-[14px]' : 'px-3 py-1 text-[13px]'
          }`}
        >
          {disabled ? 'Searching…' : 'Search'}
        </button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Top bar (results, loading, errors)
// ---------------------------------------------------------------------------

function TopBar({
  topic,
  setTopic,
  onSubmit,
  onHome,
  loading,
  meta,
}: {
  topic: string;
  setTopic: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onHome: () => void;
  loading: boolean;
  meta?: SearchResponse['meta'];
}) {
  return (
    <header className="sticky top-0 z-20 shrink-0 border-b border-line bg-surface">
      <div className="flex h-12 items-center gap-4 px-4">
        <button
          type="button"
          onClick={onHome}
          className="shrink-0 rounded-sm text-[14px] font-semibold tracking-tight text-ink"
        >
          <span className="hidden sm:inline">Research Copilot</span>
          <span className="sm:hidden" aria-label="Research Copilot">RC</span>
        </button>
        <div className="mx-auto w-full min-w-0 max-w-[560px]">
          <SearchField topic={topic} setTopic={setTopic} onSubmit={onSubmit} size="sm" disabled={loading} />
        </div>
        <div className="hidden w-[180px] shrink-0 justify-end md:flex">
          {meta && (
            <p
              className="text-[12px] text-muted tabular-nums"
              title={meta.cache_path === 'warm' ? 'Served from the semantic cache' : 'Fetched live from arXiv'}
            >
              {meta.cache_path === 'warm' ? 'from cache' : 'live from arXiv'} · {meta.latency_seconds.toFixed(1)} s
            </p>
          )}
        </div>
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------
// Results
// ---------------------------------------------------------------------------

/** Three panes on wide screens: ranked list | reader | map. Stacks below 1024px. */
const PANES =
  'flex flex-1 flex-col lg:grid lg:min-h-0 lg:grid-cols-[340px_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)_400px] xl:grid-cols-[340px_minmax(0,1fr)_minmax(0,1fr)] xl:grid-rows-1';
const LIST_PANE = 'border-b border-line bg-surface lg:row-span-2 lg:overflow-y-auto lg:border-b-0 lg:border-r xl:row-span-1';
const READER_PANE = 'flex min-h-0 min-w-0 flex-col border-b border-line bg-surface lg:border-b-0 xl:border-r';
const MAP_PANE = 'h-[560px] lg:col-start-2 lg:row-start-2 lg:h-auto lg:min-h-0 lg:border-t lg:border-line xl:col-start-3 xl:row-start-1 xl:border-t-0';

function ResultsView({
  results,
  searched,
  selectedPaper,
  view,
  setView,
  onOpenPaper,
}: {
  results: SearchResponse;
  searched: string;
  selectedPaper: Paper | null;
  view: 'synthesis' | 'paper';
  setView: (v: 'synthesis' | 'paper') => void;
  onOpenPaper: (p: Paper) => void;
}) {
  const rankedTitles = useMemo(() => results.papers.map((p) => p.title), [results.papers]);
  const shownPaper = view === 'paper' ? selectedPaper : null;

  const onMapSelect = (title: string | null) => {
    const hit = title ? results.papers.find((p) => p.title === title) : undefined;
    if (hit) onOpenPaper(hit);
  };

  return (
    <div className={PANES}>
      <aside className={LIST_PANE} aria-label="Ranked papers">
        <div className="sticky top-0 z-10 flex h-10 items-center justify-between border-b border-line bg-surface px-4">
          <h2 className="text-[13px] font-medium text-ink">
            Ranked papers
            <span className="ml-2 font-mono text-[12px] font-normal text-muted tabular-nums">{results.papers.length}</span>
          </h2>
          <span className="text-[12px] text-muted">by relevance</span>
        </div>
        <ol>
          {results.papers.map((p, i) => (
            <li key={p.arxiv_id} className="border-b border-line last:border-b-0">
              <PaperRow
                paper={p}
                rank={i + 1}
                active={shownPaper?.arxiv_id === p.arxiv_id}
                onClick={() => onOpenPaper(p)}
              />
            </li>
          ))}
        </ol>
      </aside>

      <section className={READER_PANE} aria-label="Reader">
        <div className="flex h-10 shrink-0 items-stretch gap-5 border-b border-line px-4 sm:px-8" role="tablist">
          <Tab active={view === 'synthesis'} onClick={() => setView('synthesis')}>
            Synthesis
          </Tab>
          <Tab active={view === 'paper'} onClick={() => setView('paper')} disabled={!selectedPaper}>
            Paper
            {selectedPaper && (
              <span className="ml-1.5 font-mono text-[12px] text-muted tabular-nums">
                {results.papers.findIndex((p) => p.arxiv_id === selectedPaper.arxiv_id) + 1}
              </span>
            )}
          </Tab>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-8 sm:py-8">
          {view === 'synthesis' || !selectedPaper ? (
            <Synthesis results={results} searched={searched} onOpenPaper={onOpenPaper} />
          ) : (
            <PaperReader paper={selectedPaper} />
          )}
        </div>
      </section>

      <section className={MAP_PANE} aria-label="Reading map">
        <ReadingMap
          data={results.graph}
          rankedTitles={rankedTitles}
          selectedTitle={shownPaper ? shownPaper.title : null}
          onSelectTitle={onMapSelect}
        />
      </section>
    </div>
  );
}

function Tab({
  active,
  onClick,
  disabled,
  children,
}: {
  active: boolean;
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      disabled={disabled}
      className={`-mb-px flex items-center border-b-2 text-[13px] font-medium transition-colors duration-[120ms] disabled:cursor-not-allowed disabled:opacity-40 ${
        active ? 'border-accent text-ink' : 'border-transparent text-muted hover:text-ink'
      }`}
    >
      {children}
    </button>
  );
}

function firstAuthor(p: Paper) {
  if (!p.authors?.length) return 'Unknown';
  const surname = p.authors[0].trim().split(/\s+/).pop();
  return p.authors.length > 1 ? `${surname} et al.` : surname;
}

/** Wraps query terms found in the text in <mark>, like a reader's highlighter. */
function Highlight({ text, terms }: { text: string; terms?: string[] }) {
  const words = (terms ?? []).filter((t) => t.length > 1);
  if (!words.length) return <>{text}</>;
  const escaped = words.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).sort((a, b) => b.length - a.length);
  const word = `(?:${escaped.join('|')})\\w*`;
  const re = new RegExp(`\\b(${word}(?:[\\s-]+${word})*)`, 'gi');
  const parts = text.split(re);
  return (
    <>
      {parts.map((part, i) => (i % 2 === 1 ? <mark key={i}>{part}</mark> : <React.Fragment key={i}>{part}</React.Fragment>))}
    </>
  );
}

function PaperRow({
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
  const score = Math.max(0, Math.min(1, paper.relevance_score ?? 0));
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? 'true' : undefined}
      className={`grid w-full grid-cols-[20px_minmax(0,1fr)] gap-x-2 px-4 py-3 text-left transition-colors duration-[120ms] ${
        active ? 'bg-surface-2' : 'hover:bg-surface-2'
      }`}
    >
      <span className={`pt-[3px] font-mono text-[12px] tabular-nums ${active ? 'text-accent' : 'text-muted'}`}>{rank}</span>
      <span className="flex min-w-0 flex-col gap-1.5">
        <span className="font-serif text-[15px] font-semibold leading-snug text-ink">
          <Highlight text={paper.title} terms={paper.matched_terms} />
        </span>
        <span className="truncate text-[12px] text-muted tabular-nums">
          {firstAuthor(paper)} · {paper.published?.slice(0, 4)} · {paper.categories?.[0]}
        </span>
        <span className="flex items-center gap-2" title="Relevance to your topic (0 to 1)">
          <span className="h-[2px] flex-1 bg-line">
            <span className="block h-full bg-accent" style={{ width: `${score * 100}%` }} />
          </span>
          <span className="font-mono text-[12px] text-ink-2 tabular-nums">{score.toFixed(3)}</span>
        </span>
      </span>
    </button>
  );
}

function Synthesis({
  results,
  searched,
  onOpenPaper,
}: {
  results: SearchResponse;
  searched: string;
  onOpenPaper: (p: Paper) => void;
}) {
  const paragraphs = results.synthesis.split(/\n\s*\n/).filter((s) => s.trim());
  return (
    <article className="max-w-[68ch]">
      <p className="text-[12px] text-muted">
        Across {results.papers.length} papers on <span className="text-ink-2">“{searched}”</span>
      </p>
      <h2 className="mt-1 font-serif text-[24px] font-semibold leading-tight text-ink">Synthesis</h2>
      <div className="mt-5 flex flex-col gap-4 font-serif text-[17px] leading-[1.65] text-ink">
        {paragraphs.map((para, i) => (
          <p key={i}>{para}</p>
        ))}
      </div>

      <h3 className="mb-2 mt-10 text-[11px] font-medium uppercase tracking-[0.06em] text-muted">Drawn from</h3>
      <ol className="border-t border-line">
        {results.papers.map((p, i) => (
          <li key={p.arxiv_id} className="border-b border-line">
            <button
              type="button"
              onClick={() => onOpenPaper(p)}
              className="flex w-full items-baseline gap-3 py-2 text-left transition-colors duration-[120ms] hover:text-accent"
            >
              <span className="w-4 shrink-0 font-mono text-[12px] text-muted tabular-nums">{i + 1}</span>
              <span className="min-w-0 flex-1 text-[14px]">{p.title}</span>
              <span className="shrink-0 text-[12px] text-muted tabular-nums">
                {firstAuthor(p)} {p.published?.slice(0, 4)}
              </span>
            </button>
          </li>
        ))}
      </ol>
    </article>
  );
}

function PaperReader({ paper }: { paper: Paper }) {
  const s = paper.summary;
  const grounding = s?.grounding;
  const groundPct = grounding ? Math.round(grounding.score * 100) : null;
  const weak = groundPct !== null && groundPct < 50;

  return (
    <article className="max-w-[68ch]">
      <p className="font-mono text-[12px] text-muted">
        arXiv:{paper.arxiv_id} · {paper.categories?.slice(0, 3).join(' ')}
      </p>
      <h2 className="mt-2 font-serif text-[26px] font-semibold leading-[1.2] text-ink [text-wrap:balance]">
        {paper.title}
      </h2>
      <p className="mt-3 text-[14px] leading-relaxed text-ink-2">{paper.authors.join(', ')}</p>
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-[13px]">
        <span className="font-mono text-muted">{paper.published}</span>
        <a
          href={paper.arxiv_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 rounded-sm text-accent underline-offset-4 hover:underline"
        >
          arXiv page <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
        </a>
        <a
          href={paper.pdf_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 rounded-sm text-accent underline-offset-4 hover:underline"
        >
          PDF <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
        </a>
      </div>

      {s ? (
        <>
          <p className="mt-8 border-l-2 border-line pl-4 font-serif text-[19px] leading-[1.55] text-ink">{s.tldr}</p>

          <div className="mt-8 flex flex-col gap-7">
            <ReaderSection label="Problem">{s.problem}</ReaderSection>
            <ReaderSection label="Method">{s.methods}</ReaderSection>
            <BenchmarksPanel benchmarks={s.benchmarks} />
          </div>

          {grounding && (
            <div className="mt-8 border-t border-line pt-4 text-[13px]">
              <p className={`flex items-start gap-2 ${weak ? 'text-warn' : 'text-ink-2'}`}>
                {weak ? (
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                ) : (
                  <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted" aria-hidden />
                )}
                <span>
                  Summary check: <span className="font-mono tabular-nums">{groundPct}%</span> of the summary’s key
                  terms appear in the abstract.{weak ? ' Read the abstract before relying on this summary.' : ''}
                </span>
              </p>
              {grounding.unsupported.length > 0 && (
                <details className="mt-2 pl-[22px]">
                  <summary className="cursor-pointer rounded-sm text-muted hover:text-ink">
                    {grounding.unsupported.length} terms not found in the abstract
                  </summary>
                  <p className="mt-2 flex flex-wrap gap-1.5">
                    {grounding.unsupported.map((t) => (
                      <span key={t} className="rounded-sm bg-surface-2 px-1.5 py-0.5 font-mono text-[12px] text-ink-2">
                        {t}
                      </span>
                    ))}
                  </p>
                </details>
              )}
            </div>
          )}
        </>
      ) : (
        <p className="mt-8 text-[14px] text-muted">No summary for this paper. The abstract is below.</p>
      )}

      {paper.abstract && (
        <details className="mt-6 border-t border-line pt-4" open={!s}>
          <summary className="cursor-pointer rounded-sm text-[13px] font-medium text-ink-2 hover:text-ink">Abstract</summary>
          <p className="mt-3 font-serif text-[16px] leading-[1.65] text-ink-2">{paper.abstract}</p>
        </details>
      )}
    </article>
  );
}

function ReaderSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-1.5 text-[11px] font-medium uppercase tracking-[0.06em] text-muted">{label}</h3>
      <p className="font-serif text-[16px] leading-[1.65] text-ink">{children || '—'}</p>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Loading and messages
// ---------------------------------------------------------------------------

function LoadingView({ step, topic }: { step: number; topic: string }) {
  const current = PIPELINE_STEPS[Math.max(0, step)];
  return (
    <div className={PANES} aria-busy="true">
      <aside className={LIST_PANE}>
        <div className="flex h-10 items-center border-b border-line px-4">
          <h2 className="text-[13px] font-medium text-ink">Ranked papers</h2>
        </div>
        <ol className="flex flex-col gap-2.5 px-4 py-4" aria-label="Search progress">
          {PIPELINE_STEPS.map((s, i) => {
            const done = i < step;
            const now = i === step;
            return (
              <li key={s.name} className="flex items-center gap-2.5 text-[13px]">
                <span
                  className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border ${
                    done ? 'border-accent bg-accent text-accent-ink' : now ? 'border-accent' : 'border-line'
                  }`}
                  aria-hidden
                >
                  {done && <Check className="h-3 w-3" strokeWidth={3} />}
                </span>
                <span className={done ? 'text-ink-2' : now ? 'font-medium text-ink' : 'text-muted'}>{s.doing}</span>
              </li>
            );
          })}
        </ol>
        <div className="border-t border-line" aria-hidden>
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="grid grid-cols-[20px_1fr] gap-x-2 border-b border-line px-4 py-3">
              <span className="font-mono text-[12px] text-line">{i + 1}</span>
              <span className="flex flex-col gap-2">
                <span className="h-3 w-11/12 rounded-sm bg-surface-2" />
                <span className="h-3 w-3/5 rounded-sm bg-surface-2" />
                <span className="h-2.5 w-2/5 rounded-sm bg-surface-2" />
              </span>
            </div>
          ))}
        </div>
      </aside>

      <section className={READER_PANE}>
        <div className="flex h-10 shrink-0 items-center border-b border-line px-4 sm:px-8">
          <span className="text-[13px] font-medium text-muted">Synthesis</span>
        </div>
        <div className="px-4 py-8 sm:px-8">
          <p className="text-[12px] text-muted">Searching for</p>
          <p className="mt-1 font-serif text-[24px] font-semibold leading-tight text-ink">“{topic}”</p>
          <p className="mt-4 max-w-[52ch] text-[14px] leading-relaxed text-ink-2">
            {current.doing}. A new topic usually takes 10 to 20 seconds; topics searched before come from the cache
            and return faster.
          </p>
        </div>
      </section>

      <section className={`${MAP_PANE} flex flex-col bg-surface`}>
        <div className="flex h-10 shrink-0 items-center border-b border-line px-4">
          <span className="text-[13px] font-medium text-muted">Reading map</span>
        </div>
        <div className="flex flex-1 items-center justify-center p-6 text-center text-[13px] text-muted">
          The map of related papers appears here when results arrive.
        </div>
      </section>
    </div>
  );
}

function StateMessage({
  title,
  body,
  action,
  tone,
}: {
  title: string;
  body: React.ReactNode;
  action?: React.ReactNode;
  tone?: 'warn';
}) {
  return (
    <main className="mx-auto w-full max-w-[640px] px-4 py-16 sm:px-6">
      <div className="flex gap-3">
        {tone === 'warn' && <AlertTriangle className="mt-1 h-4 w-4 shrink-0 text-warn" aria-hidden />}
        <div className="min-w-0">
          <h2 className="font-serif text-[22px] font-semibold leading-tight text-ink">{title}</h2>
          <p className="mt-2 break-words text-[14px] leading-relaxed text-ink-2">{body}</p>
          {action && <div className="mt-5">{action}</div>}
        </div>
      </div>
    </main>
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
    return <ReaderSection label="Benchmarks">{benchmarks}</ReaderSection>;
  }

  if (Array.isArray(benchmarks) && benchmarks.length > 0) {
    const rows = benchmarks as BenchmarkRow[];
    return (
      <section>
        <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.06em] text-muted">Benchmarks</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-muted">
                <th className="py-2 pr-4 font-medium">Dataset</th>
                <th className="py-2 pr-4 font-medium">Metric</th>
                <th className="py-2 pr-4 text-right font-medium">Result</th>
                <th className="py-2 text-right font-medium">Baseline</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((b, i) => (
                <tr key={i} className="border-b border-line last:border-0">
                  <td className="py-2 pr-4 text-ink">{b.dataset}</td>
                  <td className="py-2 pr-4 text-ink-2">{b.metric}</td>
                  <td className="py-2 pr-4 text-right font-mono font-medium text-ink tabular-nums">{b.result}</td>
                  <td className="py-2 text-right font-mono text-muted tabular-nums">{b.baseline}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    );
  }

  return null;
}

import React, { useEffect, useMemo, useRef, useState } from 'react';
import Head from 'next/head';
import dynamic from 'next/dynamic';
import { AlertTriangle, ArrowUpRight, Check, Info } from 'lucide-react';
import { Paper, SearchResponse, acceptBackend, backendHint, getApiBase, pendingLinkBackend, safeArxivUrl } from '../lib/api';
import { Cursor, PixelMark, PixelMeter, PixelProgress, Pixels, RevealWords, ScrollInk } from '../components/Motion';

/*
 * Design rules: .claude/skills/kavosh-ui/SKILL.md
 * Tokens (bg-page, text-ink, border-line, ...) and keyframes live in styles/globals.css.
 */

const ReadingMap = dynamic(() => import('../components/ReadingMap'), { ssr: false });

type BenchmarkRow = {
  dataset: string;
  metric: string;
  result: string;
  baseline: string;
};

type Health = { status: string; embed_model?: string; llm_model?: string; hybrid_retrieval?: boolean };

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

const LABEL = 'font-mono text-[11px] uppercase tracking-[0.14em]';

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
  // A backend named in the share link, waiting for the visitor to accept it.
  const [linkBackend, setLinkBackend] = useState<string | null>(null);
  const [apiBase, setApiBase] = useState<string | null>(null);

  useEffect(() => {
    setLinkBackend(pendingLinkBackend());
    setApiBase(getApiBase());
  }, []);

  useEffect(() => {
    if (!apiBase) return;
    setHealth(null);
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 3000);
    fetch(`${apiBase}/health`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((h: Health) => setHealth(h))
      .catch(() => setHealth('offline'))
      .finally(() => clearTimeout(timer));
    return () => ctrl.abort();
  }, [apiBase]);

  const decideLinkBackend = (accept: boolean) => {
    acceptBackend(accept ? linkBackend : null);
    setLinkBackend(null);
    setApiBase(getApiBase());
  };

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

      const res = await fetch(`${getApiBase()}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: trimmed, max_results: 5 }),
        // A hung backend should end in an error, not an endless loading screen.
        signal: AbortSignal.timeout(120_000),
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
        err instanceof DOMException && err.name === 'TimeoutError'
          ? 'The search took longer than 2 minutes and was stopped.'
          : err instanceof Error
            ? err.message
            : 'Search failed. The search service did not respond.'
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
        <title>Kavosh</title>
        <meta name="description" content="Kavosh (Persian for exploration) finds, ranks, summarises and maps arXiv papers on a research topic." />
      </Head>

      {linkBackend && <LinkBackendBar url={linkBackend} onDecide={decideLinkBackend} />}

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
                  {backendHint().long}
                </>
              }
              action={
                searched ? (
                  <button
                    type="button"
                    onClick={() => handleSearch(undefined, searched)}
                    className={`${LABEL} rounded-full border border-accent px-4 py-2 text-accent transition-colors duration-200 hover:bg-accent hover:text-accent-ink`}
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

/** Asks before using a backend named in a share link (anyone can make one). */
function LinkBackendBar({ url, onDecide }: { url: string; onDecide: (accept: boolean) => void }) {
  const host = (() => {
    try {
      return new URL(url).host;
    } catch {
      return url;
    }
  })();
  return (
    <div role="alertdialog" aria-label="Connect search to a shared backend" className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-[1180px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-8">
        <p className="min-w-0 flex-1 text-[14px] text-ink-2">
          This link connects search to <span className="break-all font-mono text-[13px] text-ink">{host}</span>. Connect
          only if you trust the person who sent it.
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onDecide(false)}
            className={`${LABEL} rounded-full border border-line px-4 py-2 text-ink-2 transition-colors duration-200 hover:border-accent hover:text-accent`}
          >
            Ignore
          </button>
          <button
            type="button"
            onClick={() => onDecide(true)}
            className={`${LABEL} rounded-full bg-cta px-4 py-2 text-cta-ink transition-opacity duration-200 hover:opacity-85`}
          >
            Connect
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Start page
// ---------------------------------------------------------------------------

const HERO_LINES = ['Every paper on your topic.', 'Ranked by meaning.', 'Summarised, then checked.', 'Mapped by how they connect.'];

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
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="relative">
      <header className="sticky top-0 z-30 border-b border-line bg-page">
        <nav className="flex h-16 items-center justify-between gap-4 px-4 sm:px-8">
          <a href="#top" className="flex items-center gap-2.5 rounded-sm">
            <PixelMark size={18} />
            <span className="text-[17px] font-semibold tracking-[-0.02em]">Kavosh</span>
          </a>
          <div className="flex items-center gap-6">
            <a href="#how" className={`${LABEL} hidden rounded-sm text-ink-2 transition-colors hover:text-accent sm:block`}>
              How it works
            </a>
            <button
              type="button"
              onClick={() => inputRef.current?.focus()}
              className={`${LABEL} rounded-full border border-accent px-4 py-2 text-accent transition-colors duration-200 hover:bg-accent hover:text-accent-ink`}
            >
              Start searching
            </button>
          </div>
        </nav>
        <StatusBar health={health} />
      </header>

      <section id="top" className="relative overflow-hidden">
        <Pixels className="hidden md:block" />
        <div className="relative mx-auto max-w-[1180px] px-4 pb-24 pt-[9vh] sm:px-8 md:pl-[14%]">
          <h1 className="text-[clamp(38px,4.7vw,66px)] font-medium leading-[1.06] tracking-[-0.035em]">
            {HERO_LINES.map((line, i) => {
              const before = HERO_LINES.slice(0, i).join(' ').split(' ').filter(Boolean).length;
              return (
                <span key={line} className="block">
                  <RevealWords text={line} delay={150 + before * 70} step={70} />
                </span>
              );
            })}
          </h1>

          <div className="mt-10 max-w-[720px] animate-rise" style={{ animationDelay: '500ms' }}>
            <SearchField
              topic={topic}
              setTopic={setTopic}
              onSubmit={onSubmit}
              size="lg"
              autoFocus
              inputRef={inputRef}
            />
            <div className="mt-5 flex flex-wrap items-baseline gap-x-5 gap-y-2.5">
              <span className={`${LABEL} text-muted`}>Try</span>
              {EXAMPLES.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => onExample(q)}
                  className={`${LABEL} group rounded-sm text-ink-2 transition-colors duration-200 hover:text-accent`}
                >
                  {q}
                  <span className="ml-1 inline-block transition-transform duration-200 group-hover:translate-x-1">›</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="how" className="border-t border-line">
        <div className="mx-auto flex max-w-[1180px] flex-col gap-10 px-4 py-[18vh] sm:px-8 md:pl-[14%]">
          <p className={`${LABEL} text-muted`}>What happens when you search</p>
          {[
            'Type a topic.',
            'We pull up to 30 candidate papers from arXiv.',
            `${embed ?? 'An embedding model'} ranks every abstract against your words.`,
            `${llm ?? 'A language model'} writes the TL;DR, problem, method and benchmarks for each paper.`,
            'Then checks each summary against its abstract.',
            'And maps which papers sit close together.',
            'That’s your reading list.',
          ].map((line) => (
            <ScrollInk key={line} className="max-w-[22ch] text-[32px] font-medium leading-[1.12] tracking-[-0.03em] sm:text-[46px]">
              {line}
            </ScrollInk>
          ))}
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="px-4 pb-8 pt-14 sm:px-8">
          <p
            aria-hidden
            className="select-none text-[clamp(72px,21vw,320px)] font-medium uppercase leading-[0.86] tracking-[-0.045em] text-ink"
          >
            Kavosh
          </p>
          <p className="mt-4 flex items-baseline gap-3 text-ink-2">
            <span lang="fa" dir="rtl" className="text-[22px]">کاوش</span>
            <span className={`${LABEL} text-muted`}>Persian for exploration</span>
          </p>
          <div className={`${LABEL} mt-10 flex flex-wrap items-center justify-between gap-4 text-muted`}>
            <span>Thank you to arXiv for use of its open access interoperability.</span>
            <a href="#top" className="rounded-sm transition-colors hover:text-accent">
              Back to top ↑
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function StatusBar({ health }: { health: Health | null | 'offline' }) {
  return (
    <div className={`${LABEL} flex h-10 items-center justify-center gap-3 overflow-hidden border-t border-line px-4 text-ink-2`}>
      {health === null && <span className="text-muted">Checking the backend</span>}
      {health === 'offline' && (
        <span className="flex items-center gap-2 truncate text-warn">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
          {backendHint().short}
        </span>
      )}
      {health && health !== 'offline' && (
        <span className="flex min-w-0 items-center gap-2.5">
          <span className="h-2 w-2 shrink-0 animate-blink bg-accent" aria-hidden />
          <span className="truncate">
            Live on arXiv
            {health.embed_model && <span className="hidden sm:inline"> · embeddings {health.embed_model}</span>}
            {health.llm_model && <span className="hidden md:inline"> · summaries {health.llm_model}</span>}
            {health.hybrid_retrieval ? ' · hybrid retrieval' : ''}
          </span>
        </span>
      )}
    </div>
  );
}

function SearchField({
  topic,
  setTopic,
  onSubmit,
  size,
  disabled,
  autoFocus,
  inputRef,
}: {
  topic: string;
  setTopic: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  size: 'lg' | 'sm';
  disabled?: boolean;
  autoFocus?: boolean;
  inputRef?: React.RefObject<HTMLInputElement | null>;
}) {
  const lg = size === 'lg';
  return (
    <form onSubmit={onSubmit} role="search" className="w-full">
      <div
        className={`flex items-center rounded-full border border-line bg-surface transition-[border-color,box-shadow] duration-200 focus-within:border-accent focus-within:shadow-[0_0_0_4px_var(--mark)] ${
          lg ? 'h-16 pl-6 pr-2' : 'h-10 pl-4 pr-1'
        }`}
      >
        <span className={`${LABEL} shrink-0 text-accent ${lg ? '' : 'hidden sm:inline'}`} aria-hidden>
          ›
        </span>
        <input
          ref={inputRef}
          id={lg ? 'topic-start' : 'topic-bar'}
          autoFocus={autoFocus}
          className={`min-w-0 flex-1 bg-transparent text-ink outline-none placeholder:text-muted disabled:opacity-60 ${
            lg ? 'px-3 text-[18px]' : 'px-2 text-[14px]'
          }`}
          placeholder="Type a research topic"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          disabled={disabled}
          aria-label="Research topic"
        />
        <button
          type="submit"
          disabled={disabled || !topic.trim()}
          className={`${LABEL} shrink-0 rounded-full bg-cta text-cta-ink transition-[opacity,background-color] duration-200 hover:opacity-85 disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-muted ${
            lg ? 'px-6 py-3.5' : 'px-4 py-2'
          }`}
        >
          {disabled ? 'Searching' : 'Search'}
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
    <header className="sticky top-0 z-20 shrink-0 border-b border-line bg-page">
      <div className="flex h-14 items-center gap-4 px-4">
        <button type="button" onClick={onHome} className="flex shrink-0 items-center gap-2 rounded-sm" aria-label="Kavosh, start page">
          <PixelMark size={16} />
          <span className="hidden text-[15px] font-semibold tracking-[-0.02em] sm:inline">Kavosh</span>
        </button>
        <div className="mx-auto w-full min-w-0 max-w-[600px]">
          <SearchField topic={topic} setTopic={setTopic} onSubmit={onSubmit} size="sm" disabled={loading} />
        </div>
        <div className="hidden w-[190px] shrink-0 justify-end md:flex">
          {meta && (
            <p
              className={`${LABEL} flex items-center gap-2 text-muted`}
              title={meta.cache_path === 'warm' ? 'Served from the semantic cache' : 'Fetched live from arXiv'}
            >
              <span className={`h-1.5 w-1.5 ${meta.cache_path === 'warm' ? 'bg-ink-2' : 'bg-accent'}`} aria-hidden />
              {meta.cache_path === 'warm' ? 'Cached' : 'Live'} · {meta.latency_seconds.toFixed(1)} s
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
  'flex flex-1 flex-col lg:grid lg:min-h-0 lg:grid-cols-[360px_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)_400px] xl:grid-cols-[360px_minmax(0,1fr)_minmax(0,1fr)] xl:grid-rows-1';
const LIST_PANE = 'border-b border-line bg-page lg:row-span-2 lg:overflow-y-auto lg:border-b-0 lg:border-r xl:row-span-1';
const READER_PANE = 'flex min-h-0 min-w-0 flex-col border-b border-line bg-surface lg:border-b-0 xl:border-r';
const MAP_PANE = 'h-[560px] lg:col-start-2 lg:row-start-2 lg:h-auto lg:min-h-0 lg:border-t lg:border-line xl:col-start-3 xl:row-start-1 xl:border-t-0';
const PANE_HEAD = 'flex h-11 shrink-0 items-center justify-between gap-3 border-b border-line px-4';

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
        <div className={`${PANE_HEAD} sticky top-0 z-10 bg-page`}>
          <h2 className={`${LABEL} text-ink`}>
            Ranked papers <span className="text-muted">/ {results.papers.length}</span>
          </h2>
          <span className={`${LABEL} text-muted`}>Relevance</span>
        </div>
        <ol>
          {results.papers.map((p, i) => (
            <li
              key={p.arxiv_id}
              className="animate-rise border-b border-line last:border-b-0"
              style={{ animationDelay: `${i * 70}ms` }}
            >
              <PaperRow
                paper={p}
                rank={i + 1}
                active={shownPaper?.arxiv_id === p.arxiv_id}
                onClick={() => onOpenPaper(p)}
                delay={250 + i * 70}
              />
            </li>
          ))}
        </ol>
      </aside>

      <section className={READER_PANE} aria-label="Reader">
        <div className={`${PANE_HEAD} justify-start gap-6 sm:px-8`} role="tablist">
          <Tab active={view === 'synthesis'} onClick={() => setView('synthesis')}>
            Synthesis
          </Tab>
          <Tab active={view === 'paper'} onClick={() => setView('paper')} disabled={!selectedPaper}>
            Paper
            {selectedPaper && (
              <span className="ml-1.5 text-muted">
                {String(results.papers.findIndex((p) => p.arxiv_id === selectedPaper.arxiv_id) + 1)}
              </span>
            )}
          </Tab>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-8 sm:px-10 sm:py-10">
          {view === 'synthesis' || !selectedPaper ? (
            <Synthesis key={`syn-${searched}`} results={results} searched={searched} onOpenPaper={onOpenPaper} />
          ) : (
            <PaperReader key={selectedPaper.arxiv_id} paper={selectedPaper} />
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
      className={`${LABEL} relative flex h-full items-center transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-40 ${
        active ? 'text-ink' : 'text-muted hover:text-ink'
      }`}
    >
      {children}
      <span
        aria-hidden
        className={`absolute inset-x-0 -bottom-px h-[2px] origin-left bg-accent transition-transform duration-300 ease-[var(--ease-out-soft)] ${
          active ? 'scale-x-100' : 'scale-x-0'
        }`}
      />
    </button>
  );
}

function firstAuthor(p: Paper) {
  if (!p.authors?.length) return 'Unknown';
  const surname = p.authors[0].trim().split(/\s+/).pop();
  return p.authors.length > 1 ? `${surname} et al.` : surname;
}

/** Wraps runs of query terms found in the text in <mark>, like a reader's highlighter. */
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
  delay,
}: {
  paper: Paper;
  rank: number;
  active: boolean;
  onClick: () => void;
  delay: number;
}) {
  const score = Math.max(0, Math.min(1, paper.relevance_score ?? 0));
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? 'true' : undefined}
      className={`group relative grid w-full grid-cols-[24px_minmax(0,1fr)] gap-x-2 px-4 py-4 text-left transition-colors duration-200 ${
        active ? 'bg-surface' : 'hover:bg-surface'
      }`}
    >
      <span
        aria-hidden
        className={`absolute inset-y-0 left-0 w-[3px] origin-top bg-accent transition-transform duration-300 ease-[var(--ease-out-soft)] ${
          active ? 'scale-y-100' : 'scale-y-0'
        }`}
      />
      <span className={`pt-[2px] font-mono text-[12px] tabular-nums ${active ? 'text-accent' : 'text-muted'}`}>
        {String(rank).padStart(2, '0')}
      </span>
      <span className="flex min-w-0 flex-col gap-2">
        <span className="text-[15px] font-medium leading-snug tracking-[-0.01em] text-ink">
          <Highlight text={paper.title} terms={paper.matched_terms} />
        </span>
        <span className="truncate text-[12px] text-muted tabular-nums">
          {firstAuthor(paper)} · {paper.published?.slice(0, 4)} · <span className="font-mono">{paper.categories?.[0]}</span>
        </span>
        <span className="flex items-center gap-3" title="Relevance to your topic (0 to 1)">
          <PixelMeter value={score} delay={delay} />
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
  // The LLM sometimes adds markdown bold; show the words, not the asterisks.
  const paragraphs = results.synthesis
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .split(/\n\s*\n/)
    .filter((s) => s.trim());
  return (
    <article className="max-w-[68ch]">
      <p className={`${LABEL} text-accent`}>Synthesis · {results.papers.length} papers</p>
      <h2 className="mt-3 animate-rise text-[30px] font-medium leading-[1.1] tracking-[-0.03em] text-ink sm:text-[38px]">
        “{searched}”
      </h2>
      <div className="mt-8 flex flex-col gap-5 text-[17px] leading-[1.7] text-ink">
        {paragraphs.map((para, i) => (
          <p key={i}>
            <RevealWords text={para} delay={200 + i * 400} step={9} />
          </p>
        ))}
      </div>

      <h3 className={`${LABEL} mb-3 mt-12 text-muted`}>Drawn from</h3>
      <ol className="border-t border-line">
        {results.papers.map((p, i) => (
          <li key={p.arxiv_id} className="border-b border-line">
            <button
              type="button"
              onClick={() => onOpenPaper(p)}
              className="group flex w-full items-baseline gap-4 py-3 text-left transition-colors duration-200 hover:text-accent"
            >
              <span className="w-5 shrink-0 font-mono text-[12px] text-muted tabular-nums">{String(i + 1).padStart(2, '0')}</span>
              <span className="min-w-0 flex-1 text-[14px] font-medium">{p.title}</span>
              <span className="shrink-0 text-[12px] text-muted tabular-nums">
                {firstAuthor(p)} {p.published?.slice(0, 4)}
              </span>
              <span className="shrink-0 text-muted transition-transform duration-200 group-hover:translate-x-1 group-hover:text-accent">›</span>
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
      <p className={`${LABEL} text-muted`}>
        arXiv:{paper.arxiv_id} · {paper.categories?.slice(0, 3).join(' ')}
      </p>
      <h2 className="mt-3 animate-rise text-[28px] font-medium leading-[1.12] tracking-[-0.03em] text-ink [text-wrap:balance] sm:text-[34px]">
        {paper.title}
      </h2>
      <p className="mt-4 animate-rise text-[14px] leading-relaxed text-ink-2" style={{ animationDelay: '80ms' }}>
        {paper.authors.join(', ')}
      </p>
      <div className="mt-4 flex animate-rise flex-wrap items-center gap-3" style={{ animationDelay: '140ms' }}>
        <span className="mr-2 font-mono text-[12px] text-muted">{paper.published}</span>
        {safeArxivUrl(paper.arxiv_url) && (
        <a
          href={safeArxivUrl(paper.arxiv_url)}
          target="_blank"
          rel="noreferrer"
          className={`${LABEL} inline-flex items-center gap-1 rounded-full border border-line px-3.5 py-1.5 text-ink-2 transition-colors duration-200 hover:border-accent hover:text-accent`}
        >
          arXiv page <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
        </a>
        )}
        {safeArxivUrl(paper.pdf_url) && (
        <a
          href={safeArxivUrl(paper.pdf_url)}
          target="_blank"
          rel="noreferrer"
          className={`${LABEL} inline-flex items-center gap-1 rounded-full border border-accent px-3.5 py-1.5 text-accent transition-colors duration-200 hover:bg-accent hover:text-accent-ink`}
        >
          PDF <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
        </a>
        )}
      </div>

      {s ? (
        <>
          <p className="mt-10 text-[22px] font-medium leading-[1.4] tracking-[-0.015em]">
            <RevealWords text={s.tldr} delay={200} step={30} />
          </p>

          <div className="mt-10 flex animate-rise flex-col gap-8" style={{ animationDelay: '400ms' }}>
            <ReaderSection label="Problem">{s.problem}</ReaderSection>
            <ReaderSection label="Method">{s.methods}</ReaderSection>
            <BenchmarksPanel benchmarks={s.benchmarks} />
          </div>

          {grounding && (
            <div className="mt-10 border-t border-line pt-5 text-[13px]">
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
        <details className="mt-6 border-t border-line pt-5" open={!s}>
          <summary className={`${LABEL} cursor-pointer rounded-sm text-ink-2 hover:text-accent`}>Abstract</summary>
          <p className="mt-4 text-[16px] leading-[1.7] text-ink-2">{paper.abstract}</p>
        </details>
      )}
    </article>
  );
}

function ReaderSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-2 sm:grid-cols-[110px_minmax(0,1fr)] sm:gap-6">
      <h3 className={`${LABEL} pt-1 text-accent`}>{label}</h3>
      <p className="text-[16px] leading-[1.7] text-ink">{children || '—'}</p>
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
        <div className={PANE_HEAD}>
          <h2 className={`${LABEL} text-ink`}>Ranked papers</h2>
          <span className={`${LABEL} text-muted tabular-nums`}>
            {Math.max(0, step) + 1}/{PIPELINE_STEPS.length}
          </span>
        </div>
        <div className="flex flex-col gap-4 px-4 py-5">
          <PixelProgress step={step} steps={PIPELINE_STEPS.length} />
          <ol className="flex flex-col gap-2.5" aria-label="Search progress">
            {PIPELINE_STEPS.map((s, i) => {
              const done = i < step;
              const now = i === step;
              return (
                <li key={s.name} className={`${LABEL} flex items-center gap-2.5`}>
                  <span
                    className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center ${
                      done ? 'bg-accent text-accent-ink' : now ? 'border border-accent' : 'border border-line'
                    }`}
                    aria-hidden
                  >
                    {done && <Check className="h-2.5 w-2.5" strokeWidth={3} />}
                  </span>
                  <span className={done ? 'text-ink-2' : now ? 'text-ink' : 'text-muted'}>
                    {s.doing}
                    {now && <Cursor />}
                  </span>
                </li>
              );
            })}
          </ol>
        </div>
        <div className="border-t border-line" aria-hidden>
          {[0, 1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="grid animate-rise grid-cols-[24px_1fr] gap-x-2 border-b border-line px-4 py-4"
              style={{ animationDelay: `${i * 90}ms` }}
            >
              <span className="font-mono text-[12px] text-ghost">{String(i + 1).padStart(2, '0')}</span>
              <span className="flex flex-col gap-2">
                <span className="h-3 w-11/12 bg-surface-2" />
                <span className="h-3 w-3/5 bg-surface-2" />
                <span className="mt-1 flex gap-[2px]">
                  {Array.from({ length: 20 }, (_, k) => (
                    <span key={k} className="h-[6px] flex-1 bg-surface-2" />
                  ))}
                </span>
              </span>
            </div>
          ))}
        </div>
      </aside>

      <section className={READER_PANE}>
        <div className={`${PANE_HEAD} sm:px-8`}>
          <span className={`${LABEL} text-muted`}>Synthesis</span>
        </div>
        <div className="px-4 py-10 sm:px-10">
          <p className={`${LABEL} text-accent`}>Searching</p>
          <p className="mt-3 text-[30px] font-medium leading-[1.1] tracking-[-0.03em] sm:text-[38px]">
            <RevealWords text={`“${topic}”`} step={60} />
          </p>
          <p className="mt-5 max-w-[52ch] text-[15px] leading-relaxed text-ink-2">
            {current.doing}. A new topic usually takes 10 to 20 seconds; topics searched before come from the cache and
            return faster.
          </p>
        </div>
      </section>

      <section className={`${MAP_PANE} relative flex flex-col overflow-hidden bg-surface`}>
        <div className={PANE_HEAD}>
          <span className={`${LABEL} text-muted`}>Reading map</span>
        </div>
        <div className="relative flex flex-1 items-center justify-center p-6 text-center">
          <Pixels />
          <p className={`${LABEL} relative text-muted`}>The map appears when results arrive</p>
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
    <main className="relative mx-auto w-full max-w-[720px] px-4 py-20 sm:px-6">
      <p className={`${LABEL} flex items-center gap-2 ${tone === 'warn' ? 'text-warn' : 'text-accent'}`}>
        {tone === 'warn' && <AlertTriangle className="h-3.5 w-3.5" aria-hidden />}
        {tone === 'warn' ? 'Error' : 'No results'}
      </p>
      <h2 className="mt-3 animate-rise text-[30px] font-medium leading-[1.1] tracking-[-0.03em] text-ink">{title}</h2>
      <p className="mt-4 break-words text-[15px] leading-relaxed text-ink-2">{body}</p>
      {action && <div className="mt-6">{action}</div>}
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
      <section className="grid gap-2 sm:grid-cols-[110px_minmax(0,1fr)] sm:gap-6">
        <h3 className={`${LABEL} pt-1 text-accent`}>Benchmarks</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className={`${LABEL} border-b border-line text-muted`}>
                <th className="py-2 pr-4 font-normal">Dataset</th>
                <th className="py-2 pr-4 font-normal">Metric</th>
                <th className="py-2 pr-4 text-right font-normal">Result</th>
                <th className="py-2 text-right font-normal">Baseline</th>
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

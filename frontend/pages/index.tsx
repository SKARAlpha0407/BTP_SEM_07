import React, { useState } from 'react';
import Head from 'next/head';
import { Paper, SearchResponse } from '../lib/api';
import Pipeline from '../components/Pipeline';
import dynamic from 'next/dynamic';
const ReadingMap = dynamic(() => import('../components/ReadingMap'), { ssr: false });

type BenchmarkRow = {
  dataset: string;
  metric: string;
  result: string;
  baseline: string;
};

const API_BASE = 'http://localhost:8000';

export default function Home() {
  const [topic, setTopic] = useState('');
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(-1);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = topic.trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);
    setResults(null);
    setSelectedPaper(null);

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

  return (
    <div className="min-h-screen bg-white text-gray-900 font-sans">
      <Head>
        <title>Research Copilot — arXiv Search</title>
      </Head>

      <header className="border-b border-gray-200 py-8 px-8 bg-gray-50/50 flex items-center justify-between">
        <h1 className="text-xl font-bold tracking-tight">Research Copilot</h1>
        <form onSubmit={handleSearch} className="flex gap-3 w-1/3 items-center">
          <input
            className="flex-1 px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="Enter a research topic (e.g. RAG)..."
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !topic.trim()}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:bg-blue-300 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </form>
      </header>

      <main className="p-8">
        {loading && <Pipeline currentStep={step} />}

        {error && (
          <div className="max-w-3xl mx-auto mb-8 p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
            {error}
          </div>
        )}

        {!loading && !results && !error && (
          <div className="flex flex-col items-center justify-center py-32 text-center max-w-md mx-auto">
            <div className="text-6xl mb-6">📚</div>
            <h2 className="text-2xl font-bold mb-4">Search a topic to get started</h2>
            <p className="text-gray-500">
              Enter a machine learning research area above. We'll retrieve the most
              relevant arXiv papers and generate structured summaries you can read here.
            </p>
          </div>
        )}

        {!loading && results && results.papers.length === 0 && (
          <div className="flex flex-col items-center justify-center py-32 text-center max-w-md mx-auto">
            <div className="text-6xl mb-6">🔍</div>
            <h2 className="text-2xl font-bold mb-4">No papers found</h2>
            <p className="text-gray-500">
              arXiv had no matches for "{topic}". Try a broader term or a different
              phrasing.
            </p>
          </div>
        )}

        {!loading && results && results.papers.length > 0 && (
          <div className="space-y-12">
            <section className="bg-gradient-to-br from-blue-50 to-indigo-50 p-6 rounded-2xl border border-blue-200 shadow-sm">
              <h3 className="text-sm font-bold text-blue-600 uppercase tracking-wider mb-2">
                Cross-paper Synthesis
              </h3>
              <p className="text-lg leading-relaxed text-gray-800">{results.synthesis}</p>
            </section>

            <div className="grid grid-cols-12 gap-8">
              <div className="col-span-4 space-y-4">
                <h3 className="font-bold text-gray-400 uppercase text-xs tracking-widest">
                  Ranked Papers
                </h3>
                {results.papers.map((p, i) => (
                  <div
                    key={p.arxiv_id}
                    onClick={() => setSelectedPaper(p)}
                    className={`p-4 rounded-xl cursor-pointer border transition-all ${selectedPaper?.arxiv_id === p.arxiv_id
                        ? 'border-blue-500 bg-blue-50 shadow-sm'
                        : 'border-gray-100 hover:border-gray-300 bg-white'
                      }`}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <span className="text-xs font-bold text-gray-400">#{i + 1}</span>
                      <span className="text-xs font-medium px-2 py-1 bg-blue-100 text-blue-700 rounded">
                        {((p.relevance_score ?? 0) * 100).toFixed(1)}%
                      </span>
                    </div>
                    <h4 className="font-semibold text-sm leading-snug mb-2">{p.title}</h4>
                    <div className="w-full bg-gray-100 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-blue-500 h-full"
                        style={{ width: `${(p.relevance_score ?? 0) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              <div className="col-span-8">
                {selectedPaper ? (
                  <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <div className="flex justify-between items-start">
                      <h2 className="text-3xl font-bold leading-tight">
                        {selectedPaper.title}
                      </h2>
                      <div className="flex gap-2">
                        <a
                          href={selectedPaper.arxiv_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs px-3 py-1 border rounded hover:bg-gray-50"
                        >
                          arXiv
                        </a>
                        <a
                          href={selectedPaper.pdf_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs px-3 py-1 bg-black text-white rounded hover:bg-gray-800"
                        >
                          PDF
                        </a>
                      </div>
                    </div>
                    <p className="text-gray-500 text-sm">
                      {selectedPaper.authors.join(', ')} · {selectedPaper.published}
                    </p>

                    <div className="grid grid-cols-1 gap-4">
                      <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
                        <h4 className="text-xs font-bold text-gray-400 uppercase mb-2">
                          TL;DR
                        </h4>
                        <p className="text-gray-800 font-medium">
                          {selectedPaper.summary?.tldr ?? '—'}
                        </p>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
                          <h4 className="text-xs font-bold text-gray-400 uppercase mb-2">
                            Problem
                          </h4>
                          <p className="text-sm text-gray-700">
                            {selectedPaper.summary?.problem ?? '—'}
                          </p>
                        </div>
                        <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
                          <h4 className="text-xs font-bold text-gray-400 uppercase mb-2">
                            Methods
                          </h4>
                          <p className="text-sm text-gray-700">
                            {selectedPaper.summary?.methods ?? '—'}
                          </p>
                        </div>
                      </div>
                      <BenchmarksPanel benchmarks={selectedPaper.summary?.benchmarks} />
                    </div>
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-400 border-2 border-dashed border-gray-100 rounded-3xl min-h-[300px]">
                    Select a paper to see insights
                  </div>
                )}
              </div>
            </div>

            <section className="pt-12 border-t border-gray-100">
              <h3 className="text-xl font-bold mb-6">Reading Map</h3>
              <ReadingMap data={results.graph} />
            </section>
          </div>
        )}
      </main>
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
      <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
        <h4 className="text-xs font-bold text-gray-400 uppercase mb-2">Benchmarks</h4>
        <p className="text-sm text-gray-700 whitespace-pre-wrap">{benchmarks}</p>
      </div>
    );
  }

  if (Array.isArray(benchmarks) && benchmarks.length > 0) {
    const rows = benchmarks as BenchmarkRow[];
    return (
      <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
        <h4 className="text-xs font-bold text-gray-400 uppercase mb-2">Benchmarks</h4>
        <table className="w-full text-xs text-left">
          <thead>
            <tr className="text-gray-400 border-b">
              <th className="pb-2">Dataset</th>
              <th className="pb-2">Metric</th>
              <th className="pb-2">Result</th>
              <th className="pb-2">Baseline</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((b, i) => (
              <tr key={i} className="border-b last:border-0">
                <td className="py-2 font-medium">{b.dataset}</td>
                <td className="py-2">{b.metric}</td>
                <td className="py-2 text-blue-600 font-bold">{b.result}</td>
                <td className="py-2 text-gray-500">{b.baseline}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return null;
}
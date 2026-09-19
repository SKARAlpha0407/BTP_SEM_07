
import React, { useState } from 'react';
import Head from 'next/head';
import { searchResearch, Paper, SearchResponse } from '../lib/api';
import Pipeline from '../components/Pipeline';
import ReadingMap from '../components/ReadingMap';

export default function Home() {
  const [topic, setTopic] = useState('');
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(-1);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResults(null);
    setSelectedPaper(null);
    
    try {
      // Simulate pipeline progress for UI
      for(let i=0; i<5; i++) {
        setStep(i);
        await new Promise(r => setTimeout(r, 400));
      }
      const data = await searchResearch(topic);
      setResults(data);
    } catch (err) {
      alert('Search failed. Ensure backend is running on port 8000.');
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

      <header className="border-b border-gray-100 py-6 px-8 flex items-center justify-between">
        <h1 className="text-xl font-bold tracking-tight">Research Copilot</h1>
        <form onSubmit={handleSearch} className="flex gap-2 w-1/3">
          <input 
            className="flex-1 px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="Enter a research topic (e.g. RAG)..."
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          />
          <button 
            disabled={loading}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:bg-blue-300 transition-colors"
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </form>
      </header>

      <main className="p-8">
        {loading && <Pipeline currentStep={step} />}

        {!loading && !results && (
          <div className="flex flex-col items-center justify-center py-32 text-center max-w-md mx-auto">
            <div className="text-6xl mb-6">📚</div>
            <h2 className="text-2xl font-bold mb-4">Search a topic to get started</h2>
            <p className="text-gray-500">Enter a machine learning research area above. We'll retrieve the most relevant arXiv papers and generate structured summaries you can read here.</p>
          </div>
        )}

        {results && (
          <div className="space-y-12">
            <section className="bg-blue-50 p-6 rounded-2xl border border-blue-100">
              <h3 className="text-sm font-bold text-blue-600 uppercase tracking-wider mb-2">Cross-paper Synthesis</h3>
              <p className="text-lg leading-relaxed text-gray-800">{results.synthesis}</p>
            </section>

            <div className="grid grid-cols-12 gap-8">
              <div className="col-span-4 space-y-4">
                <h3 className="font-bold text-gray-400 uppercase text-xs tracking-widest">Ranked Papers</h3>
                {results.papers.map((p, i) => (
                  <div 
                    key={p.arxiv_id}
                    onClick={() => setSelectedPaper(p)}
                    className={`p-4 rounded-xl cursor-pointer border transition-all ${
                      selectedPaper?.arxiv_id === p.arxiv_id ? 'border-blue-500 bg-blue-50 shadow-sm' : 'border-gray-100 hover:border-gray-300 bg-white'
                    }`}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <span className="text-xs font-bold text-gray-400">#{i+1}</span>
                      <span className="text-xs font-medium px-2 py-1 bg-blue-100 text-blue-700 rounded">
                        {(p.relevance_score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <h4 className="font-semibold text-sm leading-snug mb-2">{p.title}</h4>
                    <div className="w-full bg-gray-100 h-1.5 rounded-full overflow-hidden">
                      <div className="bg-blue-500 h-full" style={{ width: `${p.relevance_score * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>

              <div className="col-span-8">
                {selectedPaper ? (
                  <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <div className="flex justify-between items-start">
                      <h2 className="text-3xl font-bold leading-tight">{selectedPaper.title}</h2>
                      <div className="flex gap-2">
                        <a href={selectedPaper.arxiv_url} target="_blank" className="text-xs px-3 py-1 border rounded hover:bg-gray-50">arXiv</a>
                        <a href={selectedPaper.pdf_url} target="_blank" className="text-xs px-3 py-1 bg-black text-white rounded hover:bg-gray-800">PDF</a>
                      </div>
                    </div>
                    <p className="text-gray-500 text-sm">{selectedPaper.authors.join(', ')} · {selectedPaper.published}</p>
                    
                    <div className="grid grid-cols-1 gap-4">
                      <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
                        <h4 className="text-xs font-bold text-gray-400 uppercase mb-2">TL;DR</h4>
                        <p className="text-gray-800 font-medium">{selectedPaper.summary?.tl_dr}</p>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
                          <h4 className="text-xs font-bold text-gray-400 uppercase mb-2">Problem</h4>
                          <p className="text-sm text-gray-700">{selectedPaper.summary?.problem}</p>
                        </div>
                        <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
                          <h4 className="text-xs font-bold text-gray-400 uppercase mb-2">Methods</h4>
                          <p className="text-sm text-gray-700">{selectedPaper.summary?.methods}</p>
                        </div>
                      </div>
                      {selectedPaper.summary?.benchmarks && selectedPaper.summary.benchmarks.length > 0 && (
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
                              {selectedPaper.summary.benchmarks.map((b, i) => (
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
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-400 border-2 border-dashed border-gray-100 rounded-3xl">
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

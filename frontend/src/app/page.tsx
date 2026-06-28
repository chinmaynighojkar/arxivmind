"use client";

import { useState, useEffect } from "react";

type Tab = "ask" | "search" | "ingest" | "summarise" | "papers";

interface QueryResult {
  answer: string;
  sources: string[];
  iterations: number;
  latency_ms: number;
}

interface PaperResult {
  paper_id: string;
  title: string;
  date: string;
  section: string;
  excerpt: string;
}

interface IngestResult {
  paper_id: string;
  title: string;
  chunks_upserted: number;
}

interface SummariseResult {
  topic: string;
  summary: string;
}

interface PaperMeta {
  paper_id: string;
  title: string;
  authors: string[];
  date: string;
  category: string;
  abstract: string;
}

export default function Home() {
  const [tab, setTab] = useState<Tab>("ask");

  // Ask
  const [askQuery, setAskQuery] = useState("");
  const [askCategory, setAskCategory] = useState("");
  const [askDateFrom, setAskDateFrom] = useState("");
  const [askResult, setAskResult] = useState<QueryResult | null>(null);

  // Search
  const [searchQuery, setSearchQuery] = useState("");
  const [searchCategory, setSearchCategory] = useState("");
  const [searchResults, setSearchResults] = useState<PaperResult[]>([]);

  // Ingest
  const [ingestId, setIngestId] = useState("");
  const [ingestResult, setIngestResult] = useState<IngestResult | null>(null);

  // Summarise
  const [sumTopic, setSumTopic] = useState("");
  const [sumMaxPapers, setSumMaxPapers] = useState(5);
  const [sumResult, setSumResult] = useState<SummariseResult | null>(null);

  // Papers
  const [papers, setPapers] = useState<PaperMeta[]>([]);
  const [papersTotal, setPapersTotal] = useState<number | null>(null);
  const [papersLoading, setPapersLoading] = useState(false);
  const [papersFilter, setPapersFilter] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (tab === "papers" && papers.length === 0 && !papersLoading) {
      setPapersLoading(true);
      fetch("/api/papers")
        .then((r) => r.json())
        .then((d) => {
          setPapers(d.papers ?? []);
          setPapersTotal(d.total ?? 0);
        })
        .catch(() => setPapers([]))
        .finally(() => setPapersLoading(false));
    }
  }, [tab]);

  async function post<T>(path: string, body: object): Promise<T> {
    const res = await fetch(`/api${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? "Request failed");
    }
    return res.json();
  }

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setAskResult(null);
    try {
      const body: Record<string, string> = { query: askQuery };
      if (askCategory) body.category = askCategory;
      if (askDateFrom) body.date_from = askDateFrom;
      const data = await post<QueryResult>("/query", body);
      setAskResult(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSearchResults([]);
    try {
      const body: Record<string, string> = { query: searchQuery };
      if (searchCategory) body.category = searchCategory;
      const data = await post<{ results: PaperResult[] }>("/search", body);
      setSearchResults(data.results);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleIngest(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setIngestResult(null);
    try {
      const data = await post<IngestResult>("/ingest", { paper_id: ingestId });
      setIngestResult(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSummarise(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSumResult(null);
    try {
      const data = await post<SummariseResult>("/summarise", {
        topic: sumTopic,
        max_papers: sumMaxPapers,
      });
      setSumResult(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "ask", label: "Ask" },
    { id: "search", label: "Search Papers" },
    { id: "ingest", label: "Ingest Paper" },
    { id: "summarise", label: "Summarise Topic" },
    { id: "papers", label: "Papers" },
  ];

  return (
    <main className="max-w-3xl mx-auto px-4 py-12">
      {/* Header */}
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-white">ArxivMind</h1>
        <p className="mt-1 text-gray-400 text-sm">
          RAG over Arxiv ML papers — ask questions, search, ingest, or summarise topics
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-8 border-b border-gray-800">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => {
              setTab(t.id);
              setError(null);
            }}
            className={`px-4 py-2 text-sm font-medium rounded-t transition-colors ${
              tab === t.id
                ? "text-white border-b-2 border-blue-500"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-6 rounded-lg bg-red-950 border border-red-800 px-4 py-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* --- Ask Tab --- */}
      {tab === "ask" && (
        <div>
          <form onSubmit={handleAsk} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Question</label>
              <textarea
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-600 resize-none"
                rows={3}
                placeholder="What are the latest approaches to reducing hallucination in LLMs?"
                value={askQuery}
                onChange={(e) => setAskQuery(e.target.value)}
                required
              />
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="block text-xs text-gray-400 mb-1">Category (optional)</label>
                <input
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-600"
                  placeholder="cs.LG"
                  value={askCategory}
                  onChange={(e) => setAskCategory(e.target.value)}
                />
              </div>
              <div className="flex-1">
                <label className="block text-xs text-gray-400 mb-1">Date from (optional)</label>
                <input
                  type="date"
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-600"
                  value={askDateFrom}
                  onChange={(e) => setAskDateFrom(e.target.value)}
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={loading || !askQuery.trim()}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
            >
              {loading ? "Thinking…" : "Ask"}
            </button>
          </form>

          {askResult && (
            <div className="mt-8 space-y-4">
              <div className="bg-gray-900 rounded-lg p-5">
                <p className="text-sm text-gray-100 whitespace-pre-wrap leading-relaxed">
                  {askResult.answer}
                </p>
              </div>
              {askResult.sources.length > 0 && (
                <div>
                  <p className="text-xs text-gray-500 mb-2">Sources</p>
                  <div className="flex flex-wrap gap-2">
                    {askResult.sources.map((s) => (
                      <a
                        key={s}
                        href={`https://arxiv.org/abs/${s}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-2 py-1 bg-gray-800 hover:bg-gray-700 rounded text-xs text-blue-400 font-mono transition-colors"
                      >
                        {s}
                      </a>
                    ))}
                  </div>
                </div>
              )}
              <p className="text-xs text-gray-600">
                {askResult.iterations} iteration{askResult.iterations !== 1 ? "s" : ""} ·{" "}
                {askResult.latency_ms}ms
              </p>
            </div>
          )}
        </div>
      )}

      {/* --- Search Tab --- */}
      {tab === "search" && (
        <div>
          <form onSubmit={handleSearch} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Search query</label>
              <input
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-600"
                placeholder="LoRA fine-tuning efficient transformers"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                required
              />
            </div>
            <div className="w-1/2">
              <label className="block text-xs text-gray-400 mb-1">Category (optional)</label>
              <input
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-600"
                placeholder="cs.LG"
                value={searchCategory}
                onChange={(e) => setSearchCategory(e.target.value)}
              />
            </div>
            <button
              type="submit"
              disabled={loading || !searchQuery.trim()}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
            >
              {loading ? "Searching…" : "Search"}
            </button>
          </form>

          {searchResults.length > 0 && (
            <div className="mt-8 space-y-4">
              {searchResults.map((r) => (
                <div key={`${r.paper_id}-${r.section}`} className="bg-gray-900 rounded-lg p-4">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <a
                      href={`https://arxiv.org/abs/${r.paper_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-blue-400 hover:text-blue-300 leading-snug"
                    >
                      {r.title}
                    </a>
                    <span className="shrink-0 text-xs text-gray-500 font-mono">{r.date}</span>
                  </div>
                  <p className="text-xs text-gray-500 mb-2">
                    {r.paper_id} · {r.section}
                  </p>
                  <p className="text-xs text-gray-400 leading-relaxed">{r.excerpt}</p>
                </div>
              ))}
            </div>
          )}

          {!loading && searchResults.length === 0 && searchQuery && (
            <p className="mt-8 text-sm text-gray-600">No results yet — hit Search.</p>
          )}
        </div>
      )}

      {/* --- Ingest Tab --- */}
      {tab === "ingest" && (
        <div>
          <p className="text-sm text-gray-400 mb-5">
            Enter an Arxiv paper ID to fetch, parse, and add it to the vector store.
          </p>
          <form onSubmit={handleIngest} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Arxiv ID</label>
              <input
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-600 font-mono"
                placeholder="2312.12456"
                value={ingestId}
                onChange={(e) => setIngestId(e.target.value)}
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading || !ingestId.trim()}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
            >
              {loading ? "Ingesting…" : "Ingest"}
            </button>
          </form>

          {loading && (
            <p className="mt-6 text-sm text-gray-500">
              Fetching PDF and embedding — this can take 30–60s…
            </p>
          )}

          {ingestResult && (
            <div className="mt-8 bg-gray-900 rounded-lg p-5">
              <p className="text-green-400 text-sm font-medium mb-1">Ingestion complete</p>
              <p className="text-sm text-gray-200 mb-1">{ingestResult.title}</p>
              <p className="text-xs text-gray-500 font-mono">
                {ingestResult.paper_id} · {ingestResult.chunks_upserted} chunks upserted
              </p>
            </div>
          )}
        </div>
      )}

      {/* --- Summarise Tab --- */}
      {tab === "summarise" && (
        <div>
          <form onSubmit={handleSummarise} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Research topic</label>
              <input
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-600"
                placeholder="diffusion models for image generation"
                value={sumTopic}
                onChange={(e) => setSumTopic(e.target.value)}
                required
              />
            </div>
            <div className="w-40">
              <label className="block text-xs text-gray-400 mb-1">Max papers</label>
              <input
                type="number"
                min={1}
                max={10}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-600"
                value={sumMaxPapers}
                onChange={(e) => setSumMaxPapers(Number(e.target.value))}
              />
            </div>
            <button
              type="submit"
              disabled={loading || !sumTopic.trim()}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
            >
              {loading ? "Summarising…" : "Summarise"}
            </button>
          </form>

          {sumResult && (
            <div className="mt-8 bg-gray-900 rounded-lg p-5">
              <p className="text-xs text-gray-500 mb-3">Topic: {sumResult.topic}</p>
              <p className="text-sm text-gray-100 whitespace-pre-wrap leading-relaxed">
                {sumResult.summary}
              </p>
            </div>
          )}
        </div>
      )}
      {/* --- Papers Tab --- */}
      {tab === "papers" && (
        <div>
          {papersLoading && (
            <p className="text-sm text-gray-500">Loading papers from index…</p>
          )}

          {!papersLoading && papers.length > 0 && (
            <>
              <div className="flex items-center gap-3 mb-5">
                <input
                  className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-600"
                  placeholder="Filter by title, author, or category…"
                  value={papersFilter}
                  onChange={(e) => setPapersFilter(e.target.value)}
                />
                <span className="shrink-0 text-xs text-gray-500">
                  {papersTotal} paper{papersTotal !== 1 ? "s" : ""} indexed
                </span>
              </div>

              <div className="space-y-3">
                {papers
                  .filter((p) => {
                    if (!papersFilter.trim()) return true;
                    const q = papersFilter.toLowerCase();
                    return (
                      p.title.toLowerCase().includes(q) ||
                      p.category.toLowerCase().includes(q) ||
                      p.authors.some((a) => a.toLowerCase().includes(q))
                    );
                  })
                  .map((p) => (
                    <div key={p.paper_id} className="bg-gray-900 rounded-lg p-4">
                      <div className="flex items-start justify-between gap-3 mb-1">
                        <a
                          href={`https://arxiv.org/abs/${p.paper_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-medium text-blue-400 hover:text-blue-300 leading-snug"
                        >
                          {p.title}
                        </a>
                        <span className="shrink-0 text-xs text-gray-500 font-mono">{p.date}</span>
                      </div>
                      <p className="text-xs text-gray-500 mb-2">
                        <span className="font-mono text-gray-600">{p.paper_id}</span>
                        {" · "}
                        <span className="bg-gray-800 px-1.5 py-0.5 rounded text-gray-400">
                          {p.category}
                        </span>
                        {p.authors.length > 0 && (
                          <span className="ml-1 text-gray-600">
                            {" · "}
                            {p.authors.slice(0, 3).join(", ")}
                            {p.authors.length > 3 ? " et al." : ""}
                          </span>
                        )}
                      </p>
                      {p.abstract && (
                        <p className="text-xs text-gray-400 leading-relaxed line-clamp-3">
                          {p.abstract}
                        </p>
                      )}
                    </div>
                  ))}
              </div>
            </>
          )}

          {!papersLoading && papers.length === 0 && (
            <p className="text-sm text-gray-600">No papers found in the index.</p>
          )}
        </div>
      )}
    </main>
  );
}

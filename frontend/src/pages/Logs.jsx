import { useState, useEffect, useCallback } from 'react';
import api from '../api';

const LEVELS = ['ALL', 'DEBUG', 'INFO', 'WARNING', 'ERROR'];
const LEVEL_COLORS = {
  DEBUG: 'text-gray-500',
  INFO: 'text-blue-400',
  WARNING: 'text-amber-400',
  ERROR: 'text-red-400',
};
const PAGE_SIZE = 100;

export default function Logs() {
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [level, setLevel] = useState('ALL');
  const [module, setModule] = useState('');
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const fetchLogs = useCallback(async (newOffset = 0) => {
    setLoading(true);
    try {
      const params = { limit: PAGE_SIZE, offset: newOffset };
      if (level !== 'ALL') params.level = level;
      if (module.trim()) params.module = module.trim();
      if (search.trim()) params.search = search.trim();

      const res = await api.get('/logs/', { params });
      setEntries(res.data.entries);
      setTotal(res.data.total);
      setHasMore(res.data.has_more);
      setOffset(newOffset);
    } catch {
      // Auth redirect handled by interceptor
    } finally {
      setLoading(false);
    }
  }, [level, module, search]);

  // Fetch on filter change
  useEffect(() => {
    fetchLogs(0);
  }, [fetchLogs]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => fetchLogs(0), 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchLogs]);

  const pageStart = offset + 1;
  const pageEnd = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold">Logs</h1>
        <button
          onClick={() => setAutoRefresh(!autoRefresh)}
          className={`text-xs px-3 py-1.5 rounded border cursor-pointer transition-colors ${
            autoRefresh
              ? 'bg-emerald-600 border-emerald-600 text-white'
              : 'bg-transparent border-gray-700 text-gray-400 hover:border-gray-500'
          }`}
        >
          {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <select
          value={level}
          onChange={(e) => setLevel(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200"
        >
          {LEVELS.map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>

        <input
          type="text"
          placeholder="Filter module..."
          value={module}
          onChange={(e) => setModule(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 w-48"
        />

        <input
          type="text"
          placeholder="Search messages..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 flex-1 min-w-48"
        />

        <button
          onClick={() => fetchLogs(0)}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-300 hover:border-gray-500 cursor-pointer"
        >
          Refresh
        </button>
      </div>

      {/* Results info */}
      <div className="flex items-center justify-between mb-2 text-xs text-gray-500">
        <span>
          {total > 0
            ? `Showing ${pageStart}–${pageEnd} of ${total} entries`
            : 'No entries'}
          {loading && ' — loading...'}
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => fetchLogs(Math.max(0, offset - PAGE_SIZE))}
            disabled={offset === 0}
            className="px-2 py-1 rounded border border-gray-700 disabled:opacity-30 cursor-pointer hover:border-gray-500 disabled:cursor-default"
          >
            Newer
          </button>
          <button
            onClick={() => fetchLogs(offset + PAGE_SIZE)}
            disabled={!hasMore}
            className="px-2 py-1 rounded border border-gray-700 disabled:opacity-30 cursor-pointer hover:border-gray-500 disabled:cursor-default"
          >
            Older
          </button>
        </div>
      </div>

      {/* Log entries */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500 text-left">
                <th className="px-3 py-2 w-40">Timestamp</th>
                <th className="px-3 py-2 w-20">Level</th>
                <th className="px-3 py-2 w-48">Module</th>
                <th className="px-3 py-2">Message</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, i) => (
                <tr
                  key={`${entry.timestamp}-${i}`}
                  className="border-b border-gray-800/50 hover:bg-gray-800/30"
                >
                  <td className="px-3 py-1.5 text-gray-500 whitespace-nowrap">
                    {entry.timestamp}
                  </td>
                  <td className={`px-3 py-1.5 font-semibold ${LEVEL_COLORS[entry.level] || 'text-gray-400'}`}>
                    {entry.level}
                  </td>
                  <td className="px-3 py-1.5 text-gray-400 truncate max-w-48" title={entry.module}>
                    {entry.module}
                  </td>
                  <td className="px-3 py-1.5 text-gray-200 whitespace-pre-wrap break-all">
                    {entry.message}
                  </td>
                </tr>
              ))}
              {entries.length === 0 && !loading && (
                <tr>
                  <td colSpan={4} className="px-3 py-8 text-center text-gray-500">
                    No log entries found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

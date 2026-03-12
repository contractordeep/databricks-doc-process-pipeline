import { useEffect, useState, useRef, useCallback } from "react";
import type { DocumentListOut } from "@/lib/api";
import { api } from "@/lib/api";
import { getElementColor } from "@/lib/colors";

const PAGE_SIZE = 10;

interface Props {
  onSelect: (fileName: string) => void;
}

export function DocumentsList({ onSelect }: Props) {
  const [docs, setDocs] = useState<DocumentListOut[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const sentinelRef = useRef<HTMLDivElement>(null);
  const hasMore = docs.length < total;

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const fetchDocs = useCallback(
    async (offset: number, append: boolean) => {
      if (!append) setLoading(true);
      else setLoadingMore(true);
      try {
        const res = await api.listDocuments(PAGE_SIZE, offset, debouncedSearch);
        setDocs((prev) => (append ? [...prev, ...res.documents] : res.documents));
        setTotal(res.total);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [debouncedSearch]
  );

  useEffect(() => {
    setDocs([]);
    fetchDocs(0, false);
  }, [fetchDocs]);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading && !loadingMore) {
          fetchDocs(docs.length, true);
        }
      },
      { rootMargin: "200px" }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loading, loadingMore, docs.length, fetchDocs]);

  return (
    <div className="p-6">
      <div className="flex items-end justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold text-[var(--db-dark)]">Documents</h1>
          <p className="text-gray-400 text-sm mt-0.5">
            {total} document{total !== 1 ? "s" : ""} processed
          </p>
        </div>
        <div className="relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            placeholder="Search by name or source..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-72 pl-9 pr-3 py-2 bg-white border border-[var(--db-border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--db-accent)]/30 focus:border-[var(--db-accent)]"
          />
        </div>
      </div>

      <div className="bg-white border border-[var(--db-border)] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--db-border)] bg-gray-50/80">
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider">File Name</th>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider">Source</th>
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider">Pages</th>
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider">Elements</th>
              <th className="text-center px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wider">Types</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-[var(--db-border)]">
                  {Array.from({ length: 6 }).map((_, j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-4 bg-gray-100 rounded animate-pulse" />
                    </td>
                  ))}
                </tr>
              ))
            ) : docs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-gray-400">
                  No documents found
                </td>
              </tr>
            ) : (
              docs.map((doc) => (
                <tr
                  key={doc.file_name}
                  onClick={() => onSelect(doc.file_name)}
                  className="border-b border-[var(--db-border)] hover:bg-[var(--db-accent)]/[0.03] cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-[var(--db-dark)]">
                    {doc.file_name}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{doc.source_name}</td>
                  <td className="px-4 py-3 text-center text-gray-600">{doc.total_pages}</td>
                  <td className="px-4 py-3 text-center text-gray-600">{doc.total_elements}</td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                        doc.status === "completed"
                          ? "bg-green-50 text-green-700 ring-1 ring-green-200"
                          : doc.status === "failed"
                            ? "bg-red-50 text-red-700 ring-1 ring-red-200"
                            : "bg-gray-50 text-gray-500 ring-1 ring-gray-200"
                      }`}
                    >
                      {doc.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1 flex-wrap">
                      {(Object.entries(doc.element_types) as [string, number][])
                        .sort(([, a], [, b]) => b - a)
                        .slice(0, 4)
                        .map(([type, count]) => (
                          <span
                            key={type}
                            className="text-xs px-1.5 py-0.5 rounded"
                            style={{
                              background: getElementColor(type) + "18",
                              color: getElementColor(type),
                            }}
                          >
                            {type}: {count}
                          </span>
                        ))}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        {loadingMore && (
          <div className="text-center py-4 text-sm text-gray-400">Loading more...</div>
        )}
        <div ref={sentinelRef} className="h-1" />
      </div>
    </div>
  );
}

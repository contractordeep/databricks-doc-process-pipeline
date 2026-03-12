import { useEffect, useState } from "react";
import type { DocumentDetailOut } from "@/lib/api";
import { api } from "@/lib/api";
import { getElementColor } from "@/lib/colors";

interface Props {
  fileName: string;
  onBack: () => void;
  onPageSelect: (pageNumber: number) => void;
}

export function DocumentDetail({ fileName, onBack, onPageSelect }: Props) {
  const [doc, setDoc] = useState<DocumentDetailOut | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getDocument(fileName).then((d) => {
      setDoc(d);
      setLoading(false);
    });
  }, [fileName]);

  if (loading || !doc) {
    return (
      <div className="p-6 animate-pulse space-y-4">
        <div className="h-6 w-64 bg-gray-200 rounded" />
        <div className="h-4 w-48 bg-gray-200 rounded" />
        <div className="grid grid-cols-4 gap-4 mt-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 bg-gray-200 rounded" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <button
        onClick={onBack}
        className="text-sm text-gray-500 hover:text-[var(--db-dark)] mb-4 flex items-center gap-1"
      >
        &larr; Back to Documents
      </button>

      <div className="bg-white border border-[var(--db-border)] rounded-lg p-5 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-lg font-bold text-[var(--db-dark)]">{doc.file_name}</h1>
            <p className="text-sm text-gray-400 mt-0.5">
              Source: {doc.source_name} &middot; Parsed: {doc.parsed_at ?? "N/A"}
            </p>
          </div>
          <span
            className={`px-2.5 py-1 rounded-full text-xs font-medium ${
              doc.status === "completed"
                ? "bg-green-50 text-green-700 ring-1 ring-green-200"
                : doc.status === "failed"
                  ? "bg-red-50 text-red-700 ring-1 ring-red-200"
                  : "bg-gray-50 text-gray-500 ring-1 ring-gray-200"
            }`}
          >
            {doc.status}
          </span>
        </div>

        <div className="flex gap-8 mt-4">
          <div>
            <div className="text-2xl font-bold text-[var(--db-dark)]">{doc.total_pages}</div>
            <div className="text-xs text-gray-400 uppercase tracking-wider">Pages</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-[var(--db-dark)]">{doc.total_elements}</div>
            <div className="text-xs text-gray-400 uppercase tracking-wider">Elements</div>
          </div>
        </div>

        <div className="flex gap-2 flex-wrap mt-4">
          {(Object.entries(doc.element_types) as [string, number][])
            .sort(([, a], [, b]) => b - a)
            .map(([type, count]) => (
              <span
                key={type}
                className="text-xs px-2 py-0.5 rounded"
                style={{
                  background: getElementColor(type) + "18",
                  color: getElementColor(type),
                }}
              >
                {type}: {count}
              </span>
            ))}
        </div>
      </div>

      <h2 className="text-sm font-semibold text-[var(--db-dark)] mb-3">Pages</h2>
      <div className="grid grid-cols-3 md:grid-cols-5 lg:grid-cols-8 xl:grid-cols-10 gap-3">
        {doc.pages.map((page) => (
          <div
            key={page.page_number}
            onClick={() => onPageSelect(page.page_number)}
            className="bg-white border border-[var(--db-border)] rounded-lg p-3 hover:border-[var(--db-accent)] hover:shadow-sm cursor-pointer transition-all text-center"
          >
            <div className="text-lg font-bold text-gray-300 mb-1">
              {page.page_number + 1}
            </div>
            <div className="text-[10px] text-gray-400">
              {page.element_count} elem
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

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
      <div className="p-8 animate-pulse space-y-4">
        <div className="h-8 w-64 bg-gray-200 rounded" />
        <div className="h-4 w-48 bg-gray-200 rounded" />
        <div className="grid grid-cols-4 gap-4 mt-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 bg-gray-200 rounded" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <button
        onClick={onBack}
        className="text-sm text-blue-600 hover:text-blue-800 mb-4 flex items-center gap-1"
      >
        &larr; Back to Documents
      </button>

      <div className="bg-white border rounded-lg p-5 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">{doc.file_name}</h1>
            <p className="text-sm text-gray-500 mt-1">
              Source: {doc.source_name} &middot; Parsed: {doc.parsed_at ?? "N/A"}
            </p>
          </div>
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${
              doc.status === "completed"
                ? "bg-green-100 text-green-800"
                : doc.status === "failed"
                  ? "bg-red-100 text-red-800"
                  : "bg-gray-100 text-gray-600"
            }`}
          >
            {doc.status}
          </span>
        </div>

        <div className="flex gap-6 mt-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900">
              {doc.total_pages}
            </div>
            <div className="text-xs text-gray-500">Pages</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900">
              {doc.total_elements}
            </div>
            <div className="text-xs text-gray-500">Elements</div>
          </div>
        </div>

        <div className="flex gap-2 flex-wrap mt-4">
          {(Object.entries(doc.element_types) as [string, number][])
            .sort(([, a], [, b]) => b - a)
            .map(([type, count]) => (
              <span
                key={type}
                className="text-xs px-2 py-1 rounded-md font-medium"
                style={{
                  background: getElementColor(type) + "20",
                  color: getElementColor(type),
                  border: `1px solid ${getElementColor(type)}40`,
                }}
              >
                {type}: {count}
              </span>
            ))}
        </div>
      </div>

      <h2 className="text-lg font-semibold mb-3">Pages</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-3">
        {doc.pages.map((page) => (
          <div
            key={page.page_number}
            onClick={() => onPageSelect(page.page_number)}
            className="border rounded-lg p-4 hover:shadow-lg cursor-pointer transition-shadow bg-white text-center"
          >
            <div className="text-2xl font-bold text-gray-400 mb-2">
              {page.page_number + 1}
            </div>
            <div className="text-xs text-gray-500">
              {page.element_count} elements
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

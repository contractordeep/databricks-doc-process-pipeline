import { useEffect, useState } from "react";
import type { DocumentListOut } from "@/lib/api";
import { api } from "@/lib/api";
import { getElementColor } from "@/lib/colors";

interface Props {
  onSelect: (fileName: string) => void;
}

export function DocumentsList({ onSelect }: Props) {
  const [docs, setDocs] = useState<DocumentListOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.listDocuments().then((d) => {
      setDocs(d);
      setLoading(false);
    });
  }, []);

  const filtered = docs.filter(
    (d) =>
      d.file_name.toLowerCase().includes(search.toLowerCase()) ||
      d.source_name.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-12 bg-gray-200 rounded" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Documents</h1>
        <p className="text-gray-500 text-sm mt-1">
          {docs.length} documents processed
        </p>
      </div>

      <input
        type="text"
        placeholder="Search by file name or source..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full max-w-md mb-4 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left p-3 font-semibold">File Name</th>
              <th className="text-left p-3 font-semibold">Source</th>
              <th className="text-center p-3 font-semibold">Pages</th>
              <th className="text-center p-3 font-semibold">Elements</th>
              <th className="text-center p-3 font-semibold">Status</th>
              <th className="text-left p-3 font-semibold">Element Types</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="p-8 text-center text-gray-400"
                >
                  No documents found
                </td>
              </tr>
            ) : (
              filtered.map((doc) => (
                <tr
                  key={doc.file_name}
                  onClick={() => onSelect(doc.file_name)}
                  className="border-b hover:bg-blue-50 cursor-pointer transition-colors"
                >
                  <td className="p-3 font-medium text-blue-700">
                    {doc.file_name}
                  </td>
                  <td className="p-3 text-gray-600">{doc.source_name}</td>
                  <td className="p-3 text-center">{doc.total_pages}</td>
                  <td className="p-3 text-center">{doc.total_elements}</td>
                  <td className="p-3 text-center">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        doc.status === "completed"
                          ? "bg-green-100 text-green-800"
                          : doc.status === "failed"
                            ? "bg-red-100 text-red-800"
                            : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {doc.status}
                    </span>
                  </td>
                  <td className="p-3">
                    <div className="flex gap-1 flex-wrap">
                      {(Object.entries(doc.element_types) as [string, number][])
                        .sort(([, a], [, b]) => b - a)
                        .slice(0, 5)
                        .map(([type, count]) => (
                          <span
                            key={type}
                            className="text-xs px-1.5 py-0.5 rounded"
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
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

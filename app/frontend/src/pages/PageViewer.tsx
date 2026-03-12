import { useEffect, useState } from "react";
import type { PageDetailOut, ElementOut, DocumentDetailOut } from "@/lib/api";
import { api } from "@/lib/api";
import { getElementColor } from "@/lib/colors";
import { PageCanvas } from "@/components/PageCanvas";
import { ColorLegend } from "@/components/ColorLegend";
import { ElementPanel } from "@/components/ElementPanel";

interface Props {
  fileName: string;
  pageNumber: number;
  onBack: () => void;
  onPageChange: (pageNumber: number) => void;
}

export function PageViewer({ fileName, pageNumber, onBack, onPageChange }: Props) {
  const [page, setPage] = useState<PageDetailOut | null>(null);
  const [doc, setDoc] = useState<DocumentDetailOut | null>(null);
  const [selectedElement, setSelectedElement] = useState<ElementOut | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getPage(fileName, pageNumber),
      api.getDocument(fileName),
    ]).then(([p, d]) => {
      setPage(p);
      setDoc(d);
      setLoading(false);
    });
  }, [fileName, pageNumber]);

  if (loading || !page || !doc) {
    return (
      <div className="p-8 animate-pulse">
        <div className="h-6 w-48 bg-gray-200 rounded mb-4" />
        <div className="h-[600px] bg-gray-200 rounded" />
      </div>
    );
  }

  const totalPages = doc.pages.length;
  const hasPrev = pageNumber > 0;
  const hasNext = pageNumber < totalPages - 1;

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-auto p-6">
        <div className="flex items-center justify-between mb-4">
          <button
            onClick={onBack}
            className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
          >
            &larr; Back to {fileName}
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={() => hasPrev && onPageChange(pageNumber - 1)}
              disabled={!hasPrev}
              className="px-3 py-1 border rounded text-sm disabled:opacity-30 hover:bg-gray-50"
            >
              &larr; Prev
            </button>
            <span className="text-sm font-medium">
              Page {pageNumber + 1} of {totalPages}
            </span>
            <button
              onClick={() => hasNext && onPageChange(pageNumber + 1)}
              disabled={!hasNext}
              className="px-3 py-1 border rounded text-sm disabled:opacity-30 hover:bg-gray-50"
            >
              Next &rarr;
            </button>
          </div>
        </div>

        <div className="mb-3 flex items-center gap-4 text-sm text-gray-500">
          <span>{page.elements.length} elements</span>
        </div>

        <div className="mb-4">
          <ColorLegend />
        </div>

        {page.pdf_url ? (
          <div className="border rounded-lg bg-gray-50">
            <PageCanvas
              pdfUrl={page.pdf_url}
              pageNumber={pageNumber}
              bboxPageWidth={page.page_width}
              bboxPageHeight={page.page_height}
              elements={page.elements}
              onElementClick={setSelectedElement}
            />
          </div>
        ) : (
          <div className="border rounded-lg p-12 text-center text-gray-400 bg-gray-50">
            No PDF available
          </div>
        )}

        <div className="mt-6">
          <h3 className="text-md font-semibold mb-3">
            Elements on this page ({page.elements.length})
          </h3>
          <div className="space-y-2">
            {page.elements.map((el) => (
              <div
                key={el.element_id}
                onClick={() => setSelectedElement(el)}
                className={`border rounded-lg p-3 cursor-pointer transition-colors text-sm ${
                  selectedElement?.element_id === el.element_id
                    ? "bg-blue-50 border-blue-300"
                    : "hover:bg-gray-50"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className="text-xs px-1.5 py-0.5 rounded font-medium text-white"
                    style={{
                      background: getElementColor(el.element_type),
                    }}
                  >
                    {el.element_type}
                  </span>
                  <span className="text-xs text-gray-400">
                    #{el.element_id}
                  </span>
                </div>
                <p className="text-gray-700 line-clamp-2">
                  {el.content?.slice(0, 300) ||
                    el.ai_description?.slice(0, 300) ||
                    "No content"}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {selectedElement && (
        <ElementPanel
          element={selectedElement}
          onClose={() => setSelectedElement(null)}
        />
      )}
    </div>
  );
}

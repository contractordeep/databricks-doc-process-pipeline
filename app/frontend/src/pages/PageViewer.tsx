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
      <div className="p-6 animate-pulse">
        <div className="h-5 w-48 bg-gray-200 rounded mb-4" />
        <div className="h-[600px] bg-gray-200 rounded" />
      </div>
    );
  }

  const totalPages = doc.pages.length;
  const hasPrev = pageNumber > 0;
  const hasNext = pageNumber < totalPages - 1;

  return (
    <div className="flex h-[calc(100vh-2.75rem)]">
      <div className="flex-1 overflow-auto p-6">
        <div className="flex items-center justify-between mb-4">
          <button
            onClick={onBack}
            className="text-sm text-gray-500 hover:text-[var(--db-dark)] flex items-center gap-1"
          >
            &larr; Back to {fileName}
          </button>
          <div className="flex items-center gap-2">
            <button
              onClick={() => hasPrev && onPageChange(pageNumber - 1)}
              disabled={!hasPrev}
              className="px-2.5 py-1 border border-[var(--db-border)] rounded-md text-sm disabled:opacity-30 hover:bg-gray-50 transition-colors"
            >
              &larr;
            </button>
            <span className="text-sm font-medium text-[var(--db-dark)]">
              Page {pageNumber + 1} / {totalPages}
            </span>
            <button
              onClick={() => hasNext && onPageChange(pageNumber + 1)}
              disabled={!hasNext}
              className="px-2.5 py-1 border border-[var(--db-border)] rounded-md text-sm disabled:opacity-30 hover:bg-gray-50 transition-colors"
            >
              &rarr;
            </button>
          </div>
        </div>

        <div className="mb-3">
          <ColorLegend />
        </div>

        <div>
          {(page.image_url || page.pdf_url) ? (
            <div className="bg-white border border-[var(--db-border)] rounded-lg shadow-sm">
              <PageCanvas
                pdfUrl={page.pdf_url}
                imageUrl={page.image_url}
                pageNumber={pageNumber}
                bboxPageWidth={page.page_width}
                bboxPageHeight={page.page_height}
                elements={page.elements}
                onElementClick={setSelectedElement}
              />
            </div>
          ) : (
            <div className="border border-[var(--db-border)] rounded-lg p-12 text-center text-gray-400 bg-white">
              No PDF or image available
            </div>
          )}
        </div>

        <div className="mt-6">
          <h3 className="text-sm font-semibold text-[var(--db-dark)] mb-3">
            Elements ({page.elements.length})
          </h3>
          <div className="space-y-2">
            {page.elements.map((el) => (
              <div
                key={el.element_id}
                onClick={() => setSelectedElement(el)}
                className={`bg-white border rounded-lg p-3 cursor-pointer transition-colors text-sm ${
                  selectedElement?.element_id === el.element_id
                    ? "border-[var(--db-accent)] bg-[var(--db-accent)]/[0.03]"
                    : "border-[var(--db-border)] hover:border-gray-300"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded font-medium text-white"
                    style={{ background: getElementColor(el.element_type) }}
                  >
                    {el.element_type}
                  </span>
                  <span className="text-[10px] text-gray-400">#{el.element_id}</span>
                </div>
                <p className="text-gray-600 line-clamp-2 text-xs">
                  {el.content?.slice(0, 300) || el.ai_description?.slice(0, 300) || "No content"}
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

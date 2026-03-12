import { useRef, useState, useCallback, useEffect, useMemo } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import type { ElementOut } from "@/lib/api";
import { getElementColor } from "@/lib/colors";

pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

const PDF_OPTIONS = {
  cMapUrl: "/cmaps/",
  cMapPacked: true,
  standardFontDataUrl: "/standard_fonts/",
};
const MIN_DISPLAY_WIDTH = 320;
const VIEWER_PADDING = 32;
const INFERRED_PAGE_PADDING = 1.02;

interface PageCanvasProps {
  pdfUrl: string;
  pageNumber: number;
  bboxPageWidth: number;
  bboxPageHeight: number;
  elements: ElementOut[];
  onElementClick?: (element: ElementOut) => void;
  maxDisplayWidth?: number;
}

export function PageCanvas({
  pdfUrl,
  pageNumber,
  bboxPageWidth,
  bboxPageHeight,
  elements,
  onElementClick,
  maxDisplayWidth = 900,
}: PageCanvasProps) {
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const [canvasSize, setCanvasSize] = useState<{
    key: string;
    width: number;
    height: number;
  } | null>(null);
  const [containerWidth, setContainerWidth] = useState(maxDisplayWidth);
  const containerRef = useRef<HTMLDivElement>(null);
  const pageWrapperRef = useRef<HTMLDivElement>(null);

  const handleClick = useCallback(
    (el: ElementOut) => {
      onElementClick?.(el);
    },
    [onElementClick]
  );

  const updateCanvasSize = useCallback((key: string) => {
    const canvas = pageWrapperRef.current?.querySelector("canvas");
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      setCanvasSize({ key, width: rect.width, height: rect.height });
    }
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const updateWidth = (width: number) => {
      setContainerWidth(Math.max(MIN_DISPLAY_WIDTH, width - VIEWER_PADDING));
    };

    updateWidth(container.getBoundingClientRect().width);

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        updateWidth(entry.contentRect.width);
      }
    });

    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const displayWidth = Math.min(maxDisplayWidth, containerWidth);
  const canvasKey = `${pdfUrl}:${pageNumber}:${Math.round(displayWidth)}`;
  const activeCanvasSize = canvasSize?.key === canvasKey ? canvasSize : null;
  const hasExplicitPageSize = bboxPageWidth > 0 && bboxPageHeight > 0;
  const observedBounds = useMemo(() => {
    let maxX = 1;
    let maxY = 1;

    for (const el of elements) {
      maxX = Math.max(maxX, el.bbox_x1, el.bbox_x2);
      maxY = Math.max(maxY, el.bbox_y1, el.bbox_y2);
    }

    return { maxX, maxY };
  }, [elements]);
  const inferredSourcePageSize = useMemo(() => {
    if (hasExplicitPageSize || !activeCanvasSize) return null;

    const targetAspectRatio = activeCanvasSize.width / activeCanvasSize.height;
    if (!Number.isFinite(targetAspectRatio) || targetAspectRatio <= 0) {
      return null;
    }

    // Some parsed documents do not include page dimensions, so infer the parser
    // canvas by fitting the observed bbox extents into the rendered PDF aspect ratio.
    const width =
      Math.max(
        observedBounds.maxX,
        observedBounds.maxY * targetAspectRatio
      ) * INFERRED_PAGE_PADDING;
    const height = Math.max(
      observedBounds.maxY,
      width / targetAspectRatio
    );

    return { width, height };
  }, [activeCanvasSize, hasExplicitPageSize, observedBounds]);
  const sourcePageWidth = hasExplicitPageSize
    ? bboxPageWidth
    : inferredSourcePageSize?.width ?? activeCanvasSize?.width ?? 1;
  const sourcePageHeight = hasExplicitPageSize
    ? bboxPageHeight
    : inferredSourcePageSize?.height ?? activeCanvasSize?.height ?? 1;
  const scaleX = activeCanvasSize ? activeCanvasSize.width / sourcePageWidth : 1;
  const scaleY = activeCanvasSize ? activeCanvasSize.height / sourcePageHeight : 1;
  const clamp = (value: number, min: number, max: number) =>
    Math.min(Math.max(value, min), max);

  return (
    <div ref={containerRef} className="flex w-full justify-center overflow-auto p-4">
      <Document
        file={pdfUrl}
        options={PDF_OPTIONS}
        loading={<div className="h-[600px] w-[700px] bg-gray-100 animate-pulse rounded" />}
        error={<div className="h-[200px] flex items-center justify-center text-red-500">Failed to load PDF</div>}
      >
        <div ref={pageWrapperRef} className="relative shrink-0">
          <Page
            key={canvasKey}
            pageIndex={pageNumber}
            width={displayWidth}
            renderTextLayer={false}
            renderAnnotationLayer={false}
            onRenderSuccess={() => {
              requestAnimationFrame(() => {
                updateCanvasSize(canvasKey);
              });
            }}
          />
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: activeCanvasSize?.width ?? "100%",
              height: activeCanvasSize?.height ?? "100%",
              pointerEvents: "none",
            }}
          >
            {activeCanvasSize && elements.map((el) => {
              const left = clamp(el.bbox_x1, 0, sourcePageWidth);
              const top = clamp(el.bbox_y1, 0, sourcePageHeight);
              const right = clamp(el.bbox_x2, left, sourcePageWidth);
              const bottom = clamp(el.bbox_y2, top, sourcePageHeight);
              const x1 = left * scaleX;
              const y1 = top * scaleY;
              const w = (right - left) * scaleX;
              const h = (bottom - top) * scaleY;
              if (w <= 0 || h <= 0) return null;

              const color = getElementColor(el.element_type);
              const isHovered = hoveredId === el.element_id;
              const preview =
                el.content?.slice(0, 200) ||
                el.ai_description?.slice(0, 200) ||
                "No content";
              const labelTop = y1 < 22 ? 2 : -18;

              return (
                <div
                  key={`${el.element_id}-${el.page_id}`}
                  onMouseEnter={() => setHoveredId(el.element_id)}
                  onMouseLeave={() => setHoveredId(null)}
                  onClick={() => handleClick(el)}
                  style={{
                    position: "absolute",
                    left: x1,
                    top: y1,
                    width: w,
                    height: h,
                    border: `2px solid ${color}`,
                    background: isHovered ? `${color}40` : `${color}15`,
                    boxSizing: "border-box",
                    cursor: "pointer",
                    pointerEvents: "auto",
                    transition: "background 0.15s ease",
                    zIndex: isHovered ? 20 : 10,
                  }}
                >
                  <span
                    style={{
                      position: "absolute",
                      top: labelTop,
                      left: 0,
                      background: color,
                      color: "#fff",
                      fontSize: 9,
                      fontWeight: 700,
                      padding: "1px 4px",
                      borderRadius: 2,
                      whiteSpace: "nowrap",
                      pointerEvents: "none",
                      maxWidth: Math.max(50, Math.min(w - 4, activeCanvasSize.width - x1 - 4)),
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {el.element_type.toUpperCase().slice(0, 6)}#{el.element_id}
                  </span>

                  {isHovered && (
                    <div
                      style={{
                        position: "absolute",
                        left: Math.max(0, Math.min(10, activeCanvasSize.width - x1 - 330)),
                        top: y1 + h + 180 > activeCanvasSize.height ? -(Math.min(160, y1) + 8) : h + 4,
                        background: "rgba(255,255,255,0.97)",
                        color: "#333",
                        border: "1px solid #ccc",
                        borderRadius: 6,
                        padding: 10,
                        fontSize: 12,
                        lineHeight: 1.4,
                        maxWidth: 320,
                        zIndex: 100,
                        boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                        pointerEvents: "none",
                      }}
                    >
                      <strong style={{ color }}>{el.element_type}</strong>
                      <span style={{ marginLeft: 6, opacity: 0.6 }}>
                        #{el.element_id}
                      </span>
                      <div
                        style={{
                          marginTop: 6,
                          wordBreak: "break-word",
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {preview}
                        {(el.content?.length ?? 0) > 200 && "..."}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </Document>
    </div>
  );
}

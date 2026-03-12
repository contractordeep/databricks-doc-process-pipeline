import { useRef, useState, useCallback, useEffect } from "react";
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

interface PageCanvasProps {
  pdfUrl: string;
  imageUrl: string;
  pageNumber: number;
  bboxPageWidth: number;
  bboxPageHeight: number;
  elements: ElementOut[];
  onElementClick?: (element: ElementOut) => void;
}

export function PageCanvas({
  pdfUrl,
  imageUrl,
  pageNumber,
  bboxPageWidth,
  bboxPageHeight,
  elements,
  onElementClick,
}: PageCanvasProps) {
  if (imageUrl) {
    return (
      <ImageOverlay
        imageUrl={imageUrl}
        bboxPageWidth={bboxPageWidth}
        bboxPageHeight={bboxPageHeight}
        elements={elements}
        onElementClick={onElementClick}
      />
    );
  }

  return (
    <PdfOverlay
      pdfUrl={pdfUrl}
      pageNumber={pageNumber}
      bboxPageWidth={bboxPageWidth}
      bboxPageHeight={bboxPageHeight}
      elements={elements}
      onElementClick={onElementClick}
    />
  );
}

function ImageOverlay({
  imageUrl,
  bboxPageWidth,
  bboxPageHeight,
  elements,
  onElementClick,
}: {
  imageUrl: string;
  bboxPageWidth: number;
  bboxPageHeight: number;
  elements: ElementOut[];
  onElementClick?: (element: ElementOut) => void;
}) {
  const [naturalSize, setNaturalSize] = useState<{ width: number; height: number } | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  const onLoad = useCallback(() => {
    const img = imgRef.current;
    if (img) {
      setNaturalSize({ width: img.naturalWidth, height: img.naturalHeight });
    }
  }, []);

  const imgW = naturalSize?.width ?? 0;
  const imgH = naturalSize?.height ?? 0;
  const sourceW = bboxPageWidth > 0 ? bboxPageWidth : imgW || 1;
  const sourceH = bboxPageHeight > 0 ? bboxPageHeight : imgH || 1;
  const scaleX = imgW > 0 ? imgW / sourceW : 1;
  const scaleY = imgH > 0 ? imgH / sourceH : 1;

  return (
    <div className="overflow-auto p-4" style={{ maxHeight: "calc(100vh - 10rem)" }}>
      <div className="inline-block relative" style={{ width: imgW || "auto", height: imgH || "auto" }}>
        <img
          ref={imgRef}
          src={imageUrl}
          onLoad={onLoad}
          alt="Page"
          style={{ display: "block", width: imgW || "auto", height: imgH || "auto" }}
        />
        {naturalSize && (
          <BBoxOverlay
            elements={elements}
            scaleX={scaleX}
            scaleY={scaleY}
            sourceW={sourceW}
            sourceH={sourceH}
            canvasW={imgW}
            canvasH={imgH}
            onElementClick={onElementClick}
          />
        )}
      </div>
    </div>
  );
}

function PdfOverlay({
  pdfUrl,
  pageNumber,
  bboxPageWidth,
  bboxPageHeight,
  elements,
  onElementClick,
}: {
  pdfUrl: string;
  pageNumber: number;
  bboxPageWidth: number;
  bboxPageHeight: number;
  elements: ElementOut[];
  onElementClick?: (element: ElementOut) => void;
}) {
  const [canvasSize, setCanvasSize] = useState<{ width: number; height: number } | null>(null);
  const [containerWidth, setContainerWidth] = useState(1200);
  const containerRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const update = (w: number) => setContainerWidth(Math.max(320, w - 32));
    update(el.getBoundingClientRect().width);
    const obs = new ResizeObserver((entries) => {
      if (entries[0]) update(entries[0].contentRect.width);
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const displayWidth = Math.min(1200, containerWidth);

  const updateCanvas = useCallback(() => {
    const canvas = wrapperRef.current?.querySelector("canvas");
    if (!canvas) return;
    const r = canvas.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) setCanvasSize({ width: r.width, height: r.height });
  }, []);

  const hasExplicit = bboxPageWidth > 0 && bboxPageHeight > 0;
  let sourceW = hasExplicit ? bboxPageWidth : canvasSize?.width ?? 1;
  let sourceH = hasExplicit ? bboxPageHeight : canvasSize?.height ?? 1;

  if (!hasExplicit && canvasSize) {
    let maxX = 1, maxY = 1;
    for (const el of elements) {
      maxX = Math.max(maxX, el.bbox_x2);
      maxY = Math.max(maxY, el.bbox_y2);
    }
    const ratio = canvasSize.width / canvasSize.height;
    sourceW = Math.max(maxX, maxY * ratio) * 1.02;
    sourceH = Math.max(maxY, sourceW / ratio);
  }

  const scaleX = canvasSize ? canvasSize.width / sourceW : 1;
  const scaleY = canvasSize ? canvasSize.height / sourceH : 1;

  return (
    <div ref={containerRef} className="overflow-auto p-4" style={{ maxHeight: "calc(100vh - 10rem)" }}>
      <Document
        file={pdfUrl}
        options={PDF_OPTIONS}
        loading={<div className="h-[600px] w-[700px] bg-gray-100 animate-pulse rounded" />}
        error={<div className="h-[200px] flex items-center justify-center text-red-500">Failed to load PDF</div>}
      >
        <div ref={wrapperRef} className="relative shrink-0 inline-block">
          <Page
            pageIndex={pageNumber}
            width={displayWidth}
            renderTextLayer={false}
            renderAnnotationLayer={false}
            onRenderSuccess={() => requestAnimationFrame(updateCanvas)}
          />
          {canvasSize && (
            <BBoxOverlay
              elements={elements}
              scaleX={scaleX}
              scaleY={scaleY}
              sourceW={sourceW}
              sourceH={sourceH}
              canvasW={canvasSize.width}
              canvasH={canvasSize.height}
              onElementClick={onElementClick}
            />
          )}
        </div>
      </Document>
    </div>
  );
}

function BBoxOverlay({
  elements,
  scaleX,
  scaleY,
  sourceW,
  sourceH,
  canvasW,
  canvasH,
  onElementClick,
}: {
  elements: ElementOut[];
  scaleX: number;
  scaleY: number;
  sourceW: number;
  sourceH: number;
  canvasW: number;
  canvasH: number;
  onElementClick?: (element: ElementOut) => void;
}) {
  const [hoveredId, setHoveredId] = useState<number | null>(null);

  const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi);

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: canvasW,
        height: canvasH,
        pointerEvents: "none",
      }}
    >
      {elements.map((el) => {
        const left = clamp(el.bbox_x1, 0, sourceW);
        const top = clamp(el.bbox_y1, 0, sourceH);
        const right = clamp(el.bbox_x2, left, sourceW);
        const bottom = clamp(el.bbox_y2, top, sourceH);
        const x = left * scaleX;
        const y = top * scaleY;
        const w = (right - left) * scaleX;
        const h = (bottom - top) * scaleY;
        if (w <= 0 || h <= 0) return null;

        const color = getElementColor(el.element_type);
        const isHovered = hoveredId === el.element_id;
        const preview = el.content?.slice(0, 200) || el.ai_description?.slice(0, 200) || "No content";
        const labelTop = y < 22 ? 2 : -18;

        return (
          <div
            key={`${el.element_id}-${el.page_id}`}
            onMouseEnter={() => setHoveredId(el.element_id)}
            onMouseLeave={() => setHoveredId(null)}
            onClick={() => onElementClick?.(el)}
            style={{
              position: "absolute",
              left: x,
              top: y,
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
            {isHovered && (
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
                  maxWidth: Math.max(50, Math.min(w - 4, canvasW - x - 4)),
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {el.element_type.toUpperCase().slice(0, 6)}#{el.element_id}
              </span>
            )}

            {isHovered && (
              <div
                style={{
                  position: "absolute",
                  left: Math.max(0, Math.min(10, canvasW - x - 330)),
                  top: y + h + 180 > canvasH ? -(Math.min(160, y) + 8) : h + 4,
                  background: "rgba(255,255,255,0.97)",
                  color: "#333",
                  border: "1px solid #ddd",
                  borderRadius: 6,
                  padding: 10,
                  fontSize: 12,
                  lineHeight: 1.4,
                  maxWidth: 320,
                  zIndex: 100,
                  boxShadow: "0 4px 12px rgba(0,0,0,0.12)",
                  pointerEvents: "none",
                }}
              >
                <strong style={{ color }}>{el.element_type}</strong>
                <span style={{ marginLeft: 6, opacity: 0.5 }}>#{el.element_id}</span>
                <div style={{ marginTop: 6, wordBreak: "break-word", whiteSpace: "pre-wrap" }}>
                  {preview}
                  {(el.content?.length ?? 0) > 200 && "..."}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

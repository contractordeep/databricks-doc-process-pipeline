import { useRef, useState, useCallback } from "react";
import type { ElementOut } from "@/lib/api";
import { getElementColor } from "@/lib/colors";

interface PageCanvasProps {
  imageUrl: string;
  imageWidth: number;
  imageHeight: number;
  elements: ElementOut[];
  onElementClick?: (element: ElementOut) => void;
  maxDisplayWidth?: number;
}

export function PageCanvas({
  imageUrl,
  imageWidth,
  imageHeight,
  elements,
  onElementClick,
  maxDisplayWidth = 1200,
}: PageCanvasProps) {
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const scaleFactor =
    imageWidth > maxDisplayWidth ? maxDisplayWidth / imageWidth : 1;
  const displayWidth = Math.round(imageWidth * scaleFactor);
  const displayHeight = Math.round(imageHeight * scaleFactor);

  const handleClick = useCallback(
    (el: ElementOut) => {
      onElementClick?.(el);
    },
    [onElementClick]
  );

  return (
    <div className="relative inline-block" ref={containerRef}>
      <img
        src={imageUrl}
        alt="Document page"
        width={displayWidth}
        height={displayHeight}
        style={{ display: "block", width: displayWidth, height: displayHeight }}
        draggable={false}
      />
      {elements.map((el) => {
        const x1 = el.bbox_x1 * scaleFactor;
        const y1 = el.bbox_y1 * scaleFactor;
        const w = (el.bbox_x2 - el.bbox_x1) * scaleFactor;
        const h = (el.bbox_y2 - el.bbox_y1) * scaleFactor;
        if (w <= 0 || h <= 0) return null;

        const color = getElementColor(el.element_type);
        const isHovered = hoveredId === el.element_id;
        const preview =
          el.content?.slice(0, 200) ||
          el.ai_description?.slice(0, 200) ||
          "No content";

        return (
          <div
            key={el.element_id}
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
              cursor: "pointer",
              transition: "background 0.15s ease",
              zIndex: isHovered ? 20 : 10,
            }}
          >
            {/* Label */}
            <span
              style={{
                position: "absolute",
                top: y1 >= 18 ? -18 : 2,
                left: 0,
                background: color,
                color: "#fff",
                fontSize: 9,
                fontWeight: 700,
                padding: "1px 4px",
                borderRadius: 2,
                whiteSpace: "nowrap",
                pointerEvents: "none",
                maxWidth: Math.max(50, w - 4),
                overflow: "hidden",
              }}
            >
              {el.element_type.toUpperCase().slice(0, 6)}#{el.element_id}
            </span>

            {/* Tooltip on hover */}
            {isHovered && (
              <div
                style={{
                  position: "absolute",
                  left: 10,
                  top: h + 4,
                  background: "rgba(255,255,255,0.97)",
                  color: "#333",
                  border: "1px solid #ccc",
                  borderRadius: 6,
                  padding: 10,
                  fontSize: 12,
                  lineHeight: 1.4,
                  maxWidth: 400,
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
  );
}

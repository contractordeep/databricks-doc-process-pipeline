import type { ElementOut } from "@/lib/api";
import { getElementColor } from "@/lib/colors";

interface ElementPanelProps {
  element: ElementOut | null;
  onClose: () => void;
}

export function ElementPanel({ element, onClose }: ElementPanelProps) {
  if (!element) return null;

  const color = getElementColor(element.element_type);
  const isTable = element.element_type === "table";
  const isFigure = element.element_type === "figure";

  return (
    <div className="border-l bg-white w-96 flex-shrink-0 overflow-y-auto">
      <div className="p-4 border-b flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div
            className="w-3 h-3 rounded-sm"
            style={{ background: color }}
          />
          <span className="font-semibold text-sm">
            {element.element_type.toUpperCase()} #{element.element_id}
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 text-lg leading-none"
        >
          &times;
        </button>
      </div>

      <div className="p-4 space-y-4">
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">
            Bounding Box
          </h4>
          <p className="text-xs text-gray-600 font-mono">
            ({element.bbox_x1}, {element.bbox_y1}) &rarr; ({element.bbox_x2},{" "}
            {element.bbox_y2})
          </p>
        </div>

        {isFigure && element.ai_description && (
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">
              AI Description
            </h4>
            <p className="text-sm text-gray-700 leading-relaxed">
              {element.ai_description}
            </p>
          </div>
        )}

        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">
            Content
          </h4>
          {isTable ? (
            <div
              className="text-sm overflow-x-auto border rounded p-2"
              dangerouslySetInnerHTML={{ __html: element.content }}
            />
          ) : (
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap break-words">
              {element.content || (
                <span className="text-gray-400 italic">No content</span>
              )}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

import { ELEMENT_COLORS } from "@/lib/colors";

export function ColorLegend() {
  return (
    <div className="flex flex-wrap gap-3 p-3 bg-gray-50 rounded-lg border">
      {(Object.entries(ELEMENT_COLORS) as [string, string][]).map(([type, color]) => (
        <div key={type} className="flex items-center gap-1.5 text-xs">
          <div
            className="w-3 h-3 rounded-sm border"
            style={{ background: color, borderColor: color }}
          />
          <span className="text-gray-700">{type}</span>
        </div>
      ))}
    </div>
  );
}

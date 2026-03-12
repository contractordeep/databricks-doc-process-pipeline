import { ELEMENT_COLORS } from "@/lib/colors";

export function ColorLegend() {
  return (
    <div className="flex flex-wrap gap-3 px-3 py-2 bg-white border border-[var(--db-border)] rounded-lg">
      {(Object.entries(ELEMENT_COLORS) as [string, string][]).map(([type, color]) => (
        <div key={type} className="flex items-center gap-1.5 text-xs">
          <div
            className="w-2.5 h-2.5 rounded-sm"
            style={{ background: color }}
          />
          <span className="text-gray-500">{type}</span>
        </div>
      ))}
    </div>
  );
}

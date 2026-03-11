import { useEffect, useState } from "react";
import type { StatsOut } from "@/lib/api";
import { api } from "@/lib/api";
import { getElementColor } from "@/lib/colors";

interface Props {
  onNavigate: (page: string) => void;
}

export function Dashboard({ onNavigate }: Props) {
  const [stats, setStats] = useState<StatsOut | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getStats().then((s) => {
      setStats(s);
      setLoading(false);
    });
  }, []);

  if (loading || !stats) {
    return (
      <div className="p-8 animate-pulse space-y-6">
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 bg-gray-200 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  const successRate =
    stats.completed + stats.failed > 0
      ? ((stats.completed / (stats.completed + stats.failed)) * 100).toFixed(1)
      : "N/A";

  const typeEntries: [string, number][] = Object.entries(stats.element_type_distribution);
  const sourceEntries: [string, number][] = Object.entries(stats.source_distribution);
  const maxTypeCount = Math.max(...typeEntries.map(([, v]) => v), 1);

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          Document Processing Dashboard
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          Overview of your processed document corpus
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Documents"
          value={stats.total_documents}
          color="blue"
        />
        <StatCard label="Pages" value={stats.total_pages} color="purple" />
        <StatCard
          label="Elements"
          value={stats.total_elements}
          color="teal"
        />
        <StatCard
          label="Success Rate"
          value={`${successRate}%`}
          subtitle={`${stats.completed} completed, ${stats.failed} failed`}
          color="green"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Element type distribution */}
        <div className="border rounded-lg bg-white p-5">
          <h2 className="text-md font-semibold mb-4">
            Element Type Distribution
          </h2>
          <div className="space-y-2">
            {typeEntries
              .sort(([, a], [, b]) => b - a)
              .map(([type, count]) => (
                <div key={type} className="flex items-center gap-3">
                  <span className="text-xs w-28 text-gray-600 text-right">
                    {type}
                  </span>
                  <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${(count / maxTypeCount) * 100}%`,
                        background: getElementColor(type),
                      }}
                    />
                  </div>
                  <span className="text-xs text-gray-500 w-12 text-right font-mono">
                    {count.toLocaleString()}
                  </span>
                </div>
              ))}
          </div>
        </div>

        {/* Source distribution */}
        <div className="border rounded-lg bg-white p-5">
          <h2 className="text-md font-semibold mb-4">Documents by Source</h2>
          <div className="space-y-3">
            {sourceEntries
              .sort(([, a], [, b]) => b - a)
              .map(([source, count]) => (
                <div
                  key={source}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <span className="text-sm font-medium text-gray-700">
                    {source}
                  </span>
                  <span className="text-sm text-gray-500">
                    {count} document{count !== 1 ? "s" : ""}
                  </span>
                </div>
              ))}
          </div>

          <button
            onClick={() => onNavigate("documents")}
            className="mt-4 text-sm text-blue-600 hover:text-blue-800"
          >
            View all documents &rarr;
          </button>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  subtitle,
  color,
}: {
  label: string;
  value: string | number;
  subtitle?: string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    blue: "border-blue-200 bg-blue-50",
    purple: "border-purple-200 bg-purple-50",
    teal: "border-teal-200 bg-teal-50",
    green: "border-green-200 bg-green-50",
  };

  return (
    <div className={`border rounded-lg p-4 ${colorMap[color] ?? ""}`}>
      <div className="text-sm text-gray-600 mb-1">{label}</div>
      <div className="text-2xl font-bold text-gray-900">
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
      {subtitle && (
        <div className="text-xs text-gray-500 mt-1">{subtitle}</div>
      )}
    </div>
  );
}

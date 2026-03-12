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
      <div className="p-6 animate-pulse space-y-6">
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 bg-white rounded-lg border" />
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
        <h1 className="text-xl font-bold text-[var(--db-dark)]">
          Dashboard
        </h1>
        <p className="text-gray-500 text-sm mt-0.5">
          Overview of your processed document corpus
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Documents" value={stats.total_documents} accent="var(--db-accent)" />
        <StatCard label="Pages" value={stats.total_pages} accent="#7C3AED" />
        <StatCard label="Elements" value={stats.total_elements} accent="#0D9488" />
        <StatCard
          label="Success Rate"
          value={`${successRate}%`}
          subtitle={`${stats.completed} completed, ${stats.failed} failed`}
          accent="#059669"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-white border border-[var(--db-border)] rounded-lg p-5">
          <h2 className="text-sm font-semibold text-[var(--db-dark)] mb-4">
            Element Type Distribution
          </h2>
          <div className="space-y-2.5">
            {typeEntries
              .sort(([, a], [, b]) => b - a)
              .map(([type, count]) => (
                <div key={type} className="flex items-center gap-3">
                  <span className="text-xs w-24 text-gray-500 text-right truncate">
                    {type}
                  </span>
                  <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${(count / maxTypeCount) * 100}%`,
                        background: getElementColor(type),
                      }}
                    />
                  </div>
                  <span className="text-xs text-gray-400 w-12 text-right font-mono">
                    {count.toLocaleString()}
                  </span>
                </div>
              ))}
          </div>
        </div>

        <div className="bg-white border border-[var(--db-border)] rounded-lg p-5">
          <h2 className="text-sm font-semibold text-[var(--db-dark)] mb-4">
            Documents by Source
          </h2>
          <div className="space-y-2">
            {sourceEntries
              .sort(([, a], [, b]) => b - a)
              .map(([source, count]) => (
                <div
                  key={source}
                  className="flex items-center justify-between p-3 bg-[var(--db-surface)] rounded-lg"
                >
                  <span className="text-sm font-medium text-[var(--db-dark)]">{source}</span>
                  <span className="text-sm text-gray-400">
                    {count} doc{count !== 1 ? "s" : ""}
                  </span>
                </div>
              ))}
          </div>
          <button
            onClick={() => onNavigate("documents")}
            className="mt-4 text-sm text-[var(--db-accent)] hover:underline"
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
  accent,
}: {
  label: string;
  value: string | number;
  subtitle?: string;
  accent: string;
}) {
  return (
    <div className="bg-white border border-[var(--db-border)] rounded-lg p-4">
      <div className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">{label}</div>
      <div className="text-2xl font-bold" style={{ color: accent }}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
      {subtitle && (
        <div className="text-xs text-gray-400 mt-1">{subtitle}</div>
      )}
    </div>
  );
}

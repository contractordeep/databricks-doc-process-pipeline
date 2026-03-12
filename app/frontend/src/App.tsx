import { useState, useCallback } from "react";
import { Dashboard } from "@/pages/Dashboard";
import { DocumentsList } from "@/pages/DocumentsList";
import { DocumentDetail } from "@/pages/DocumentDetail";
import { PageViewer } from "@/pages/PageViewer";

type Route =
  | { page: "dashboard" }
  | { page: "documents" }
  | { page: "document"; fileName: string }
  | { page: "pageViewer"; fileName: string; pageNumber: number };

function App() {
  const [route, setRoute] = useState<Route>({ page: "dashboard" });

  const navigate = useCallback((page: string) => {
    if (page === "documents") setRoute({ page: "documents" });
    else setRoute({ page: "dashboard" });
  }, []);

  return (
    <div className="min-h-screen bg-[var(--db-surface)]">
      <header className="bg-[var(--db-dark)] sticky top-0 z-50">
        <div className="max-w-screen-xl mx-auto px-5 flex items-center h-11 gap-6">
          <div className="flex items-center gap-2">
            <svg width="20" height="20" viewBox="0 0 40 40" fill="none">
              <path d="M20 0L40 10L20 20L0 10L20 0Z" fill="#FF3621" />
              <path d="M40 10L20 20L0 10" stroke="#FF3621" strokeWidth="0" />
              <path d="M20 20L40 30L20 40L0 30L20 20Z" fill="#FF3621" opacity="0.6" />
            </svg>
            <span className="font-semibold text-white text-sm tracking-tight">
              Doc Viewer
            </span>
          </div>
          <nav className="flex gap-1 text-sm ml-4">
            <button
              onClick={() => setRoute({ page: "dashboard" })}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                route.page === "dashboard"
                  ? "bg-white/15 text-white"
                  : "text-white/60 hover:text-white hover:bg-white/10"
              }`}
            >
              Dashboard
            </button>
            <button
              onClick={() => setRoute({ page: "documents" })}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                route.page !== "dashboard"
                  ? "bg-white/15 text-white"
                  : "text-white/60 hover:text-white hover:bg-white/10"
              }`}
            >
              Documents
            </button>
          </nav>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto">
        {route.page === "dashboard" && <Dashboard onNavigate={navigate} />}
        {route.page === "documents" && (
          <DocumentsList
            onSelect={(fn) => setRoute({ page: "document", fileName: fn })}
          />
        )}
        {route.page === "document" && (
          <DocumentDetail
            key={route.fileName}
            fileName={route.fileName}
            onBack={() => setRoute({ page: "documents" })}
            onPageSelect={(pn) =>
              setRoute({
                page: "pageViewer",
                fileName: route.fileName,
                pageNumber: pn,
              })
            }
          />
        )}
        {route.page === "pageViewer" && (
          <PageViewer
            key={`${route.fileName}:${route.pageNumber}`}
            fileName={route.fileName}
            pageNumber={route.pageNumber}
            onBack={() =>
              setRoute({ page: "document", fileName: route.fileName })
            }
            onPageChange={(pn) =>
              setRoute({
                page: "pageViewer",
                fileName: route.fileName,
                pageNumber: pn,
              })
            }
          />
        )}
      </main>
    </div>
  );
}

export default App;

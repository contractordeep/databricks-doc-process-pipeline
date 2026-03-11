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
    <div className="min-h-screen bg-gray-50">
      {/* Top nav */}
      <header className="bg-white border-b sticky top-0 z-50">
        <div className="max-w-screen-xl mx-auto px-4 flex items-center h-12 gap-6">
          <span className="font-bold text-gray-900">Doc Viewer</span>
          <nav className="flex gap-4 text-sm">
            <button
              onClick={() => setRoute({ page: "dashboard" })}
              className={`py-3 border-b-2 transition-colors ${
                route.page === "dashboard"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              Dashboard
            </button>
            <button
              onClick={() => setRoute({ page: "documents" })}
              className={`py-3 border-b-2 transition-colors ${
                route.page !== "dashboard"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              Documents
            </button>
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-screen-xl mx-auto">
        {route.page === "dashboard" && <Dashboard onNavigate={navigate} />}
        {route.page === "documents" && (
          <DocumentsList
            onSelect={(fn) => setRoute({ page: "document", fileName: fn })}
          />
        )}
        {route.page === "document" && (
          <DocumentDetail
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

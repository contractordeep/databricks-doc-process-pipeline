export interface ElementOut {
  element_id: number;
  element_type: string;
  content: string;
  ai_description: string | null;
  page_id: number;
  bbox_x1: number;
  bbox_y1: number;
  bbox_x2: number;
  bbox_y2: number;
  bounding_box_json: string;
}

export interface PageOut {
  page_number: number;
  element_count: number;
}

export interface PageDetailOut {
  page_number: number;
  pdf_url: string;
  image_url: string;
  page_width: number;
  page_height: number;
  elements: ElementOut[];
}

export interface DocumentListOut {
  file_name: string;
  source_name: string;
  source_path: string;
  total_elements: number;
  total_pages: number;
  status: string;
  parsed_at: string | null;
  element_types: Record<string, number>;
}

export interface PaginatedDocumentsOut {
  documents: DocumentListOut[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentDetailOut extends DocumentListOut {
  pages: PageOut[];
}

export interface StatsOut {
  total_documents: number;
  total_pages: number;
  total_elements: number;
  completed: number;
  failed: number;
  element_type_distribution: Record<string, number>;
  source_distribution: Record<string, number>;
}

const BASE = "/api";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  listDocuments: (limit = 10, offset = 0, q = "") => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (q) params.set("q", q);
    return fetchJson<PaginatedDocumentsOut>(`${BASE}/documents?${params}`);
  },
  getDocument: (fileName: string) =>
    fetchJson<DocumentDetailOut>(`${BASE}/documents/${encodeURIComponent(fileName)}`),
  getPage: (fileName: string, pageNumber: number) =>
    fetchJson<PageDetailOut>(
      `${BASE}/documents/${encodeURIComponent(fileName)}/pages/${pageNumber}`
    ),
  getStats: () => fetchJson<StatsOut>(`${BASE}/stats`),
};

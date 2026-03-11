export const ELEMENT_COLORS: Record<string, string> = {
  text: "#4ECDC4",
  table: "#98D8C8",
  figure: "#45B7D1",
  title: "#FF6B6B",
  caption: "#96CEB4",
  section_header: "#FF6B6B",
  page_header: "#DDA0DD",
  page_footer: "#FFEAA7",
  page_number: "#BDC3C7",
  footnote: "#F7DC6F",
};

export function getElementColor(type: string): string {
  return ELEMENT_COLORS[type.toLowerCase()] ?? "#BDC3C7";
}

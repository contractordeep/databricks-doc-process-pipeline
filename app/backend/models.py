from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ElementOut(BaseModel):
    element_id: int
    element_type: str
    content: str = ""
    ai_description: Optional[str] = None
    page_id: int
    bbox_x1: int = 0
    bbox_y1: int = 0
    bbox_x2: int = 0
    bbox_y2: int = 0
    bounding_box_json: str = "[]"


class PageOut(BaseModel):
    page_number: int
    image_uri: str = ""
    element_count: int = 0


class PageDetailOut(BaseModel):
    page_number: int
    image_url: str
    image_width: int = 0
    image_height: int = 0
    elements: list[ElementOut] = []


class DocumentListOut(BaseModel):
    file_name: str
    source_name: str = ""
    total_elements: int = 0
    total_pages: int = 0
    status: str = "unknown"
    parsed_at: Optional[str] = None
    element_types: dict[str, int] = {}


class DocumentDetailOut(BaseModel):
    file_name: str
    source_name: str = ""
    total_elements: int = 0
    total_pages: int = 0
    status: str = "unknown"
    parsed_at: Optional[str] = None
    element_types: dict[str, int] = {}
    pages: list[PageOut] = []


class StatsOut(BaseModel):
    total_documents: int = 0
    total_pages: int = 0
    total_elements: int = 0
    completed: int = 0
    failed: int = 0
    element_type_distribution: dict[str, int] = {}
    source_distribution: dict[str, int] = {}

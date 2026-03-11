import os
import mimetypes
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from .models import (
    DocumentListOut,
    DocumentDetailOut,
    PageOut,
    ElementOut,
    PageDetailOut,
    StatsOut,
)
from .db import execute_query, fqn

api = APIRouter(prefix="/api")


@api.get("/documents", response_model=list[DocumentListOut], operation_id="listDocuments")
async def list_documents():
    elements_table = fqn("document_elements")
    pages_table = fqn("document_pages")
    log_table = fqn("processing_log")

    rows = execute_query(f"""
        SELECT
            e.file_name,
            e.source_name,
            COUNT(DISTINCT e.element_id) AS total_elements,
            COALESCE(p.total_pages, 0) AS total_pages,
            COALESCE(l.status, 'unknown') AS status,
            CAST(MIN(e.parsed_at) AS STRING) AS parsed_at
        FROM {elements_table} e
        LEFT JOIN (
            SELECT file_name, COUNT(DISTINCT page_number) AS total_pages
            FROM {pages_table}
            GROUP BY file_name
        ) p ON e.file_name = p.file_name
        LEFT JOIN (
            SELECT file_name, MAX(status) AS status
            FROM {log_table}
            GROUP BY file_name
        ) l ON e.file_name = l.file_name
        GROUP BY e.file_name, e.source_name, p.total_pages, l.status
        ORDER BY parsed_at DESC
    """)

    results = []
    for r in rows:
        type_rows = execute_query(f"""
            SELECT element_type, COUNT(*) AS cnt
            FROM {elements_table}
            WHERE file_name = '{r["file_name"]}'
            GROUP BY element_type
        """)
        element_types = {tr["element_type"]: tr["cnt"] for tr in type_rows}

        results.append(DocumentListOut(
            file_name=r["file_name"],
            source_name=r.get("source_name", ""),
            total_elements=r["total_elements"],
            total_pages=r["total_pages"],
            status=r.get("status", "unknown"),
            parsed_at=r.get("parsed_at"),
            element_types=element_types,
        ))
    return results


@api.get("/documents/{file_name}", response_model=DocumentDetailOut, operation_id="getDocument")
async def get_document(file_name: str):
    elements_table = fqn("document_elements")
    pages_table = fqn("document_pages")
    log_table = fqn("processing_log")

    elem_rows = execute_query(f"""
        SELECT element_type, COUNT(*) AS cnt
        FROM {elements_table}
        WHERE file_name = '{file_name}'
        GROUP BY element_type
    """)
    if not elem_rows:
        raise HTTPException(status_code=404, detail=f"Document '{file_name}' not found")

    element_types = {r["element_type"]: r["cnt"] for r in elem_rows}
    total_elements = sum(element_types.values())

    page_rows = execute_query(f"""
        SELECT
            page_number,
            COALESCE(image_uri, '') AS image_uri,
            COALESCE(ec.cnt, 0) AS element_count
        FROM {pages_table} pg
        LEFT JOIN (
            SELECT page_id, COUNT(*) AS cnt
            FROM {elements_table}
            WHERE file_name = '{file_name}'
            GROUP BY page_id
        ) ec ON pg.page_number = ec.page_id
        WHERE pg.file_name = '{file_name}'
        ORDER BY pg.page_number
    """)

    pages = [
        PageOut(
            page_number=r["page_number"],
            image_uri=r["image_uri"],
            element_count=r["element_count"],
        )
        for r in page_rows
    ]

    status_rows = execute_query(f"""
        SELECT MAX(status) AS status, CAST(MAX(completed_at) AS STRING) AS parsed_at,
               MAX(source_name) AS source_name
        FROM {log_table}
        WHERE file_name = '{file_name}'
    """)
    status = status_rows[0].get("status", "unknown") if status_rows else "unknown"
    parsed_at = status_rows[0].get("parsed_at") if status_rows else None
    source_name = status_rows[0].get("source_name", "") if status_rows else ""

    return DocumentDetailOut(
        file_name=file_name,
        source_name=source_name,
        total_elements=total_elements,
        total_pages=len(pages),
        status=status,
        parsed_at=parsed_at,
        element_types=element_types,
        pages=pages,
    )


@api.get(
    "/documents/{file_name}/pages/{page_number}",
    response_model=PageDetailOut,
    operation_id="getPage",
)
async def get_page(file_name: str, page_number: int):
    elements_table = fqn("document_elements")
    pages_table = fqn("document_pages")

    page_rows = execute_query(f"""
        SELECT page_number, COALESCE(image_uri, '') AS image_uri
        FROM {pages_table}
        WHERE file_name = '{file_name}' AND page_number = {page_number}
    """)
    if not page_rows:
        raise HTTPException(status_code=404, detail="Page not found")

    image_uri = page_rows[0]["image_uri"]
    image_url = f"/api/images?path={image_uri}" if image_uri else ""

    image_width, image_height = 0, 0
    if image_uri and os.path.exists(image_uri):
        try:
            from PIL import Image
            with Image.open(image_uri) as img:
                image_width, image_height = img.size
        except Exception:
            pass

    elem_rows = execute_query(f"""
        SELECT
            element_id, element_type,
            COALESCE(content, '') AS content,
            ai_description,
            page_id,
            COALESCE(bbox_x1, 0) AS bbox_x1,
            COALESCE(bbox_y1, 0) AS bbox_y1,
            COALESCE(bbox_x2, 0) AS bbox_x2,
            COALESCE(bbox_y2, 0) AS bbox_y2,
            COALESCE(bounding_box_json, '[]') AS bounding_box_json
        FROM {elements_table}
        WHERE file_name = '{file_name}' AND page_id = {page_number}
        ORDER BY element_id
    """)

    elements = [
        ElementOut(
            element_id=r["element_id"],
            element_type=r["element_type"],
            content=r["content"],
            ai_description=r.get("ai_description"),
            page_id=r["page_id"],
            bbox_x1=r["bbox_x1"],
            bbox_y1=r["bbox_y1"],
            bbox_x2=r["bbox_x2"],
            bbox_y2=r["bbox_y2"],
            bounding_box_json=r["bounding_box_json"],
        )
        for r in elem_rows
    ]

    return PageDetailOut(
        page_number=page_number,
        image_url=image_url,
        image_width=image_width,
        image_height=image_height,
        elements=elements,
    )


@api.get("/images", operation_id="getImage")
async def get_image(path: str = Query(...)):
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image not found")

    mime_type, _ = mimetypes.guess_type(path)
    if mime_type is None:
        mime_type = "image/png"

    return FileResponse(path, media_type=mime_type)


@api.get("/stats", response_model=StatsOut, operation_id="getStats")
async def get_stats():
    elements_table = fqn("document_elements")
    pages_table = fqn("document_pages")
    log_table = fqn("processing_log")

    summary = execute_query(f"""
        SELECT
            COUNT(DISTINCT file_name) AS total_documents,
            COUNT(*) AS total_elements
        FROM {elements_table}
    """)
    total_documents = summary[0]["total_documents"] if summary else 0
    total_elements = summary[0]["total_elements"] if summary else 0

    page_count = execute_query(f"SELECT COUNT(*) AS cnt FROM {pages_table}")
    total_pages = page_count[0]["cnt"] if page_count else 0

    status_rows = execute_query(f"""
        SELECT status, COUNT(DISTINCT file_name) AS cnt
        FROM {log_table}
        GROUP BY status
    """)
    completed = 0
    failed = 0
    for r in status_rows:
        if r["status"] == "completed":
            completed = r["cnt"]
        elif r["status"] == "failed":
            failed = r["cnt"]

    type_rows = execute_query(f"""
        SELECT element_type, COUNT(*) AS cnt
        FROM {elements_table}
        GROUP BY element_type
        ORDER BY cnt DESC
    """)
    element_type_distribution = {r["element_type"]: r["cnt"] for r in type_rows}

    source_rows = execute_query(f"""
        SELECT source_name, COUNT(DISTINCT file_name) AS cnt
        FROM {elements_table}
        GROUP BY source_name
        ORDER BY cnt DESC
    """)
    source_distribution = {r["source_name"]: r["cnt"] for r in source_rows}

    return StatsOut(
        total_documents=total_documents,
        total_pages=total_pages,
        total_elements=total_elements,
        completed=completed,
        failed=failed,
        element_type_distribution=element_type_distribution,
        source_distribution=source_distribution,
    )

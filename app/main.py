from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.router import api

app = FastAPI(title="Document Viewer")
app.include_router(api)

STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.exists():
    for subdir in ["assets", "cmaps", "standard_fonts"]:
        d = STATIC_DIR / subdir
        if d.exists():
            app.mount(f"/{subdir}", StaticFiles(directory=d), name=subdir)

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")

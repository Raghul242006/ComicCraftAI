from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.routes import router


settings = get_settings()

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered comic story creator using Gemini and image generation.",
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)
app.state.templates = templates

app.include_router(router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "application": settings.app_name,
        "version": settings.app_version,
        "image_backend": settings.image_backend,
    }
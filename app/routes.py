# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.schemas import PromptRequest
from app.services.image_generator import generate_image
from app.services.workflow import generate_comic


router = APIRouter()
settings = get_settings()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "index.html",
        {"title": "ComicCraft"},
    )


@router.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    story_prompt: str = Form(...),
    character_name: str = Form(...),
    setting: str = Form(...),
    tone: str = Form(...),
    art_style: str = Form(...),
    panel_count: int = Form(5),
):
    try:
        payload = PromptRequest(
            story_prompt=story_prompt,
            character_name=character_name,
            setting=setting,
            tone=tone,
            art_style=art_style,
            panel_count=panel_count,
        )

        result = await generate_comic(payload)

        return request.app.state.templates.TemplateResponse(
            request,
            "comic_preview.html",
            {"comic": result, "panels": result["panels"]},
        )

    except Exception as exc:
        return request.app.state.templates.TemplateResponse(
            request,
            "index.html",
            {"title": "ComicCraft", "error": str(exc), "form_data": {
                    "story_prompt": story_prompt,
                    "character_name": character_name,
                    "setting": setting,
                    "tone": tone,
                    "art_style": art_style,
                    "panel_count": panel_count,
                }},
            status_code=500,
        )


@router.post("/generate-comic/json")
async def generate_comic_json(payload: PromptRequest):
    try:
        result = await generate_comic(payload)

        return JSONResponse(
            content={
                "success": True,
                "message": "Comic generated successfully.",
                "panels": result["panels"],
                "pdf_url": result["pdf_url"],
            }
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@router.post("/test-image")
async def test_image(prompt: str = Form(...)):
    try:
        image_path = await generate_image(
            prompt=prompt,
            panel_number=999,
        )

        return {
            "success": True,
            "image_url": image_path,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@router.get("/export-success", response_class=HTMLResponse)
async def export_success(request: Request):
    return request.app.state.templates.TemplateResponse(request, "export_success.html")
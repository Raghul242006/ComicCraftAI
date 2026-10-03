import json
import re
from typing import List

from app.config import get_settings
from app.schemas import PanelOutline
from app.services.gemini_client import get_gemini_client


def _extract_json(text: str):
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"```$",
            "",
            text,
        )

    text = text.strip()

    start = text.find("[")
    end = text.rfind("]")

    if start == -1 or end == -1:
        raise ValueError(
            "Gemini did not return valid JSON array data."
        )

    return json.loads(text[start:end + 1])


async def generate_outline(
    story_prompt: str,
    character_name: str,
    setting: str,
    tone: str,
    art_style: str,
    panel_count: int = 5,
) -> List[PanelOutline]:

    settings = get_settings()
    client = get_gemini_client()

    if client is None:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. "
            "Add your Gemini API key to the .env file."
        )

    prompt = f"""
You are the story-planning AI for ComicCraft.

Create a cohesive {panel_count}-panel comic outline.

USER STORY IDEA:
{story_prompt}

MAIN CHARACTER:
{character_name}

SETTING:
{setting}

TONE:
{tone}

ART STYLE:
{art_style}

Requirements:

1. Exactly {panel_count} panels.
2. Keep the same main character throughout.
3. Create a clear beginning, middle, conflict and ending.
4. Every panel must logically connect to the previous panel.
5. Write a concise scene description.
6. Create a detailed image-generation prompt.
7. The image prompt must describe:
   - character appearance
   - environment
   - action
   - camera composition
   - lighting
   - art style
8. Do not place dialogue inside image_prompt.

Return ONLY valid JSON.

Expected structure:

[
  {{
    "panel_number": 1,
    "title": "Panel title",
    "scene_description": "Scene description",
    "image_prompt": "Detailed visual prompt"
  }}
]
"""

    models_to_try = [settings.gemini_outline_model]
    for fallback in ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"]:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    last_error = None
    response = None
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    "temperature": 0.8,
                    "response_mime_type": "application/json",
                },
            )
            break
        except Exception as exc:
            last_error = exc
            continue

    if response is None:
        raise RuntimeError(
            f"Failed to generate outline across models: {last_error}"
        ) from last_error

    data = _extract_json(response.text)

    panels = []

    for index, item in enumerate(data[:panel_count], start=1):
        panels.append(
            PanelOutline(
                panel_number=int(
                    item.get("panel_number", index)
                ),
                title=item.get(
                    "title",
                    f"Panel {index}",
                ),
                scene_description=item.get(
                    "scene_description",
                    "",
                ),
                image_prompt=item.get(
                    "image_prompt",
                    "",
                ),
            )
        )

    if len(panels) != panel_count:
        raise ValueError(
            f"Expected {panel_count} panels but received {len(panels)}."
        )

    return panels
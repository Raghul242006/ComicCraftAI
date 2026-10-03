import json
import re
from typing import List

from app.config import get_settings
from app.schemas import PanelOutline, PanelStory
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
            "Gemini did not return valid story JSON."
        )

    return json.loads(text[start:end + 1])


async def generate_story(
    outlines: List[PanelOutline],
    character_name: str,
    tone: str,
) -> List[PanelStory]:

    settings = get_settings()
    client = get_gemini_client()

    if client is None:
        raise RuntimeError(
            "GEMINI_API_KEY is missing."
        )

    outline_json = json.dumps(
        [panel.model_dump() for panel in outlines],
        indent=2,
    )

    prompt = f"""
You are ComicCraft's professional comic writer.

MAIN CHARACTER:
{character_name}

TONE:
{tone}

PANEL OUTLINE:
{outline_json}

Expand the outline into a polished comic script.

For every panel create:

- panel_number
- title
- scene_description
- image_prompt
- caption
- narration
- dialogue

Rules:

1. Keep the story coherent across all panels.
2. Preserve the original panel order.
3. Make dialogue natural and concise.
4. Narration should describe what is happening.
5. Caption can describe environment, mood or sound.
6. Do not introduce unnecessary characters.
7. Keep the tone consistent.
8. Keep image_prompt visually descriptive.
9. Return ONLY valid JSON.

Expected structure:

[
  {{
    "panel_number": 1,
    "title": "...",
    "scene_description": "...",
    "image_prompt": "...",
    "caption": "...",
    "narration": "...",
    "dialogue": "..."
  }}
]
"""

    models_to_try = [settings.gemini_story_model]
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
                    "temperature": 0.9,
                    "response_mime_type": "application/json",
                },
            )
            break
        except Exception as exc:
            last_error = exc
            continue

    if response is None:
        raise RuntimeError(
            f"Failed to generate story across models: {last_error}"
        ) from last_error

    data = _extract_json(response.text)

    panels = []

    for index, item in enumerate(data, start=1):
        panels.append(
            PanelStory(
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
                caption=item.get(
                    "caption",
                    "",
                ),
                narration=item.get(
                    "narration",
                    "",
                ),
                dialogue=item.get(
                    "dialogue",
                    "",
                ),
            )
        )

    return panels
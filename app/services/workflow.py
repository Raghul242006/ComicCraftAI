from app.schemas import PromptRequest
from app.services.exporters import save_pdf
from app.services.gemini_flash import generate_outline
from app.services.gemini_pro import generate_story
from app.services.image_generator import generate_image
from app.services.layout_builder import build_comic_layout


async def generate_comic(
    request: PromptRequest,
):

    # STEP 1
    # Generate structured panel outline.
    outlines = await generate_outline(
        story_prompt=request.story_prompt,
        character_name=request.character_name,
        setting=request.setting,
        tone=request.tone,
        art_style=request.art_style,
        panel_count=request.panel_count,
    )

    # STEP 2
    # Generate narration and dialogue.
    stories = await generate_story(
        outlines=outlines,
        character_name=request.character_name,
        tone=request.tone,
    )

    # STEP 3
    # Generate images.
    completed_panels = []

    for panel in stories:

        image_url = await generate_image(
            prompt=panel.image_prompt,
            panel_number=panel.panel_number,
        )

        completed_panels.append(
            {
                **panel.model_dump(),
                "image_url": image_url,
            }
        )

    # STEP 4
    # Build layout.
    layout = build_comic_layout(
        completed_panels
    )

    # STEP 5
    # Export PDF.
    pdf_url = save_pdf(
        layout
    )

    return {
        "panels": layout,
        "pdf_url": pdf_url,
    }
from typing import List

from pydantic import BaseModel, Field


class PromptRequest(BaseModel):
    story_prompt: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Main idea for the comic",
    )

    character_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    setting: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )

    tone: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    art_style: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    panel_count: int = Field(
        default=5,
        ge=3,
        le=8,
    )


class PanelOutline(BaseModel):
    panel_number: int
    title: str
    scene_description: str
    image_prompt: str


class PanelStory(BaseModel):
    panel_number: int
    title: str
    scene_description: str
    image_prompt: str
    caption: str
    narration: str
    dialogue: str = ""


class ComicResponse(BaseModel):
    success: bool
    message: str
    panels: List[PanelStory]
    pdf_url: str | None = None
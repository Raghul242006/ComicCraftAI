import asyncio
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import get_settings


def _safe_filename(text: str) -> str:
    text = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        text,
    )

    return text[:60].strip("_") or "panel"


def _create_mock_image(
    prompt: str,
    panel_number: int,
    output_path: Path,
):
    width = 1024
    height = 1024

    image = Image.new(
        "RGB",
        (width, height),
        "#e8e8e8",
    )

    draw = ImageDraw.Draw(image)

    # Border
    draw.rectangle(
        (25, 25, width - 25, height - 25),
        outline="#222222",
        width=8,
    )

    # Header
    draw.rectangle(
        (45, 45, width - 45, 150),
        fill="#222222",
    )

    try:
        font_large = ImageFont.truetype(
            "arial.ttf",
            48,
        )

        font_small = ImageFont.truetype(
            "arial.ttf",
            26,
        )

    except OSError:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text(
        (75, 75),
        f"COMICCRAFT — PANEL {panel_number}",
        fill="white",
        font=font_large,
    )

    # Comic-style placeholder
    center_x = width // 2
    center_y = 480

    draw.ellipse(
        (
            center_x - 150,
            center_y - 150,
            center_x + 150,
            center_y + 150,
        ),
        outline="#333333",
        width=10,
    )

    draw.rectangle(
        (
            center_x - 90,
            center_y + 120,
            center_x + 90,
            center_y + 320,
        ),
        outline="#333333",
        width=10,
    )

    text = (
        "Image generation is currently in MOCK mode.\n\n"
        + prompt[:220]
    )

    draw.multiline_text(
        (80, 720),
        text,
        fill="#222222",
        font=font_small,
        spacing=12,
    )

    image.save(
        output_path,
        format="PNG",
    )


async def _generate_huggingface(
    prompt: str,
    output_path: Path,
):
    settings = get_settings()

    if not settings.hf_token:
        raise RuntimeError(
            "HF_TOKEN is missing."
        )

    try:
        from huggingface_hub import InferenceClient

    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is not installed."
        ) from exc

    client = InferenceClient(
        provider="hf-inference",
        api_key=settings.hf_token,
    )

    image = client.text_to_image(
        prompt=prompt,
        model=settings.hf_image_model,
    )

    image.save(output_path)


async def _generate_diffusers(
    prompt: str,
    output_path: Path,
):
    settings = get_settings()

    try:
        import torch
        from diffusers import StableDiffusionPipeline

    except ImportError as exc:
        raise RuntimeError(
            "Local Diffusers dependencies are missing. "
            "Install torch, diffusers, transformers and accelerate."
        ) from exc

    device = (
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    dtype = (
        torch.float16
        if device == "cuda"
        else torch.float32
    )

    pipe = StableDiffusionPipeline.from_pretrained(
        settings.diffusers_model,
        torch_dtype=dtype,
    )

    pipe = pipe.to(device)

    result = pipe(
        prompt,
        num_inference_steps=20,
        guidance_scale=7.5,
    )

    image = result.images[0]

    image.save(output_path)


async def generate_image(
    prompt: str,
    panel_number: int,
) -> str:

    settings = get_settings()

    filename = (
        f"panel_{panel_number}_"
        f"{_safe_filename(prompt[:40])}.png"
    )

    output_path = (
        settings.panels_dir / filename
    )

    backend = settings.image_backend.lower()

    if backend == "mock":
        await asyncio.to_thread(
            _create_mock_image,
            prompt,
            panel_number,
            output_path,
        )

    elif backend == "hf":
        await _generate_huggingface(
            prompt,
            output_path,
        )

    elif backend == "diffusers":
        await _generate_diffusers(
            prompt,
            output_path,
        )

    else:
        raise ValueError(
            f"Unknown IMAGE_BACKEND: {backend}. "
            "Use mock, hf, or diffusers."
        )

    return f"/static/panels/{filename}"
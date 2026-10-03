from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "ComicCraft"
    app_version: str = "1.0.0"
    debug: bool = True

    gemini_api_key: str = ""

    # Current Gemini model names can be changed through .env.
    gemini_outline_model: str = "gemini-3.5-flash"
    gemini_story_model: str = "gemini-3.5-flash"

    # Image backend:
    # mock       -> local placeholders, no API required
    # hf         -> Hugging Face hosted inference
    # diffusers  -> local Stable Diffusion
    image_backend: str = "mock"

    hf_token: str = ""
    hf_image_model: str = "black-forest-labs/FLUX.1-schnell"

    diffusers_model: str = "runwayml/stable-diffusion-v1-5"

    panels_dir: Path = BASE_DIR / "static" / "panels"
    exports_dir: Path = BASE_DIR / "static" / "exports"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()

    settings.panels_dir.mkdir(parents=True, exist_ok=True)
    settings.exports_dir.mkdir(parents=True, exist_ok=True)

    return settings
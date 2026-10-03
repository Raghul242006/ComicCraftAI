from datetime import datetime
from pathlib import Path
from typing import List

from fpdf import FPDF

from app.config import get_settings


def _local_image_path(
    image_url: str,
) -> Path:

    settings = get_settings()

    filename = Path(
        image_url
    ).name

    return settings.panels_dir / filename


def _clean_text(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "—": "--",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
        "•": "*",
        "™": "(TM)",
        "©": "(C)",
        "®": "(R)",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def save_pdf(
    panels: List[dict],
) -> str:

    settings = get_settings()

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    filename = (
        f"comiccraft_{timestamp}.pdf"
    )

    output_path = (
        settings.exports_dir / filename
    )

    pdf = FPDF(
        orientation="P",
        unit="mm",
        format="A4",
    )

    pdf.set_auto_page_break(
        auto=True,
        margin=15,
    )

    for panel in panels:

        pdf.add_page()

        # Title
        pdf.set_font(
            "Helvetica",
            "B",
            20,
        )

        pdf.cell(
            0,
            12,
            _clean_text(f"Panel {panel['panel_number']}: {panel['title']}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        # Image
        image_path = _local_image_path(
            panel["image_url"]
        )

        if image_path.exists():

            pdf.image(
                str(image_path),
                x=15,
                y=30,
                w=180,
                h=120,
                keep_aspect_ratio=True,
            )

        pdf.ln(125)

        # Scene
        pdf.set_font(
            "Helvetica",
            "I",
            11,
        )

        pdf.multi_cell(
            0,
            7,
            _clean_text(panel["scene_description"]),
        )

        pdf.ln(4)

        # Caption
        pdf.set_font(
            "Helvetica",
            "B",
            11,
        )

        pdf.multi_cell(
            0,
            7,
            _clean_text(f"Caption: {panel['caption']}"),
        )

        pdf.ln(2)

        # Narration
        pdf.set_font(
            "Helvetica",
            "",
            11,
        )

        pdf.multi_cell(
            0,
            7,
            _clean_text(f"Narration: {panel['narration']}"),
        )

        # Dialogue
        if panel.get("dialogue"):

            pdf.ln(2)

            pdf.set_font(
                "Helvetica",
                "B",
                11,
            )

            pdf.multi_cell(
                0,
                7,
                _clean_text(f"Dialogue: {panel['dialogue']}"),
            )

    pdf.output(
        str(output_path)
    )

    return (
        f"/static/exports/{filename}"
    )
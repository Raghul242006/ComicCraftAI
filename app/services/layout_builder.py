from typing import List, Dict


def build_comic_layout(
    panels: List[dict],
) -> List[Dict]:

    layout = []

    for panel in panels:

        layout.append(
            {
                "panel_number": panel["panel_number"],
                "title": panel["title"],
                "image_url": panel["image_url"],
                "scene_description": panel[
                    "scene_description"
                ],
                "caption": panel["caption"],
                "narration": panel["narration"],
                "dialogue": panel.get(
                    "dialogue",
                    "",
                ),
                "image_prompt": panel[
                    "image_prompt"
                ],
            }
        )

    return layout
"""Slice 13: can the model reliably 'colour in' the building envelope?

Tests Gemini segmentation masks (denser than the sparse polygon from slice 11).
Renders the site-plan crop, asks for a building-envelope mask, overlays it in
red, and saves an image to eyeball. If the mask is clean, measuring the gap to a
mask (no coverage gaps) should beat the polygon.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice13
"""

import base64
import io
import json
import os
import re

import fitz
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv("/Users/jonosachs/Documents/Study/Tech_Projects/LLM/planning-rag/.env")

SAMPLE_PDF = "assets/site_plan.pdf"
SITE_RECT = fitz.Rect(0, 67, 1280, 400)  # site-plan viewport (deterministic from slices 4-5)
CROP_PATH = "tmp/slice13_crop.png"
OVERLAY_PATH = "tmp/slice13_overlay.png"
PROMPT = (
    "Give the segmentation mask for the proposed building footprint / building "
    "envelope on this architectural site plan. Output a JSON list where each entry "
    'has "box_2d" as [ymin, xmin, ymax, xmax] normalized 0-1000, and "mask" as a '
    "base64 PNG. Segment only the proposed building envelope."
)


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=SITE_RECT, alpha=False)
    pix.save(CROP_PATH)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    with open(CROP_PATH, "rb") as f:
        image = types.Part.from_bytes(data=f.read(), mime_type="image/png")
    resp = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[image, PROMPT],
        config={"response_mime_type": "application/json", "temperature": 0.0},
    )

    segs = json.loads(resp.text)
    print(f"model returned {len(segs)} mask(s)")
    overlay_masks(CROP_PATH, segs, OVERLAY_PATH)
    print(f"saved overlay -> {OVERLAY_PATH}")


def overlay_masks(crop_path, segs, out_path) -> None:
    base = Image.open(crop_path).convert("RGBA")
    W, H = base.size
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for s in segs:
        ymin, xmin, ymax, xmax = s["box_2d"]
        x0, y0 = int(xmin / 1000 * W), int(ymin / 1000 * H)
        x1, y1 = int(xmax / 1000 * W), int(ymax / 1000 * H)
        if x1 <= x0 or y1 <= y0:
            continue
        raw = re.sub(r"^data:image/[^;]+;base64,", "", s["mask"])
        mask = Image.open(io.BytesIO(base64.b64decode(raw))).convert("L").resize((x1 - x0, y1 - y0))
        red = Image.new("RGBA", (x1 - x0, y1 - y0), (255, 0, 0, 110))
        layer.paste(red, (x0, y0), mask)
    Image.alpha_composite(base, layer).convert("RGB").save(out_path)


if __name__ == "__main__":
    main()

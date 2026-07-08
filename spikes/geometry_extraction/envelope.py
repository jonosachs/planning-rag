"""Isolate the building envelope by having the image model colour it in.

The segmentation-mask API returned nothing usable on CAD line-art, but the
image-generation model (nano-banana / gemini-2.5-flash-image) reliably paints
the proposed building envelope in a chosen colour. We threshold that colour to a
dense mask - far cleaner than a hand-traced polygon.

IMPORTANT: the recoloured image is a REGION HINT only. Image generation
re-renders pixels and can shift lines, and it resizes the output (~4%), so never
treat it as geometry. Use the mask to answer coarse "is the building here"
questions; take precise values from dimensions, and measure against the original
vector geometry.
"""

import os

import fitz
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

IMAGE_MODEL = "gemini-2.5-flash-image"
FILL_PROMPT = (
    "Fill in the proposed building envelope (the proposed building footprint) on "
    "this site plan with solid opaque magenta. Colour only the proposed building. "
    "Keep every line, dimension and label exactly where it is - do not move or "
    "redraw anything."
)


def fill_building_envelope(
    pdf_path: str,
    page_number: int,
    rect: fitz.Rect,
    coloured_path: str,
    input_path: str,
    zoom: float = 3.0,
) -> tuple[int, int]:
    """Render the viewport, have the model colour the envelope. Returns crop px size."""
    page = fitz.open(pdf_path)[page_number]
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
    pix.save(input_path)

    client = genai.Client(api_key=_require_key())
    with open(input_path, "rb") as f:
        image = types.Part.from_bytes(data=f.read(), mime_type="image/png")
    response = client.models.generate_content(model=IMAGE_MODEL, contents=[image, FILL_PROMPT])
    parts = [p for p in response.candidates[0].content.parts if getattr(p, "inline_data", None)]
    if not parts:
        raise RuntimeError("image model returned no image part")
    with open(coloured_path, "wb") as f:
        f.write(parts[0].inline_data.data)
    return pix.width, pix.height


def envelope_mask(coloured_path: str, size: tuple[int, int]) -> np.ndarray:
    """Boolean mask of the magenta fill, resized to the input crop pixel size."""
    out = Image.open(coloured_path).convert("RGB").resize(size)
    a = np.asarray(out).astype(int)
    return (a[:, :, 0] > 140) & (a[:, :, 2] > 110) & (a[:, :, 1] < 110)


def _require_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not found")
    return key

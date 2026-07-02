from src.drawings.schemas import PdfTextFeature
from pathlib import Path
import fitz

PLANNING_KEYWORDS = [
    "site statistics",
    "site area",
    "permeability",
    "private open space",
    "g.f.a",
    "p.o.s",
    "s.p.o.s",
    "setback",
    "overshadow",
    "shadow",
    "height",
    "building height",
    "coverage",
    "boundary",
    "easement",
    "secluded private open space",
]


def parse_block_as_text_feature(page_num, block) -> PdfTextFeature | None:
    x0, y0, x1, y1, text, block_no, block_type = block
    cleaned = text.lower().replace("\n", " ").strip()

    if not is_planning_relevant(cleaned, PLANNING_KEYWORDS):
        return None

    text_feature = PdfTextFeature(
        page=page_num,
        text=cleaned,
        bbox=(x0, y0, x1, y1),
        block_no=block_no,
        block_type=block_type,
    )

    return text_feature


def is_planning_relevant(text, keywords) -> bool:
    return any(word in text for word in keywords)


def render(page, output_path, max_width=1600) -> str:
    zoom = max_width / page.rect.width
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    output_path = Path(output_path)
    pix.save(output_path)
    return str(output_path)


def render_pages(pages) -> dict:
    paths = {}
    for page in pages:
        page_num = page.number + 1
        path = render(page, f"tmp/p{page_num}.png")
        paths[page_num] = path

    print(f"Rendered {len(paths)} pages..")
    return paths

import fitz
from src.drawings.clean import parse_block_as_text_feature
from src.drawings.schemas import PageFeautres, PdfTextFeature


def extract_pages(pdf_path: str) -> fitz.Document:
    pages = fitz.open(pdf_path)
    return pages


def get_planning_relevant_pages(pages, excluded_dwgs) -> list[fitz.Page]:
    page_wh = (pages[0].rect.width, pages[0].rect.height)
    clip_wh = (0.875, 0.75)
    title_block_bbox = get_title_block_bbox(page_wh, clip_wh)

    included = []

    for page in pages:
        text = page.get_text(clip=title_block_bbox).lower()
        exclude = any(title in text for title in excluded_dwgs)
        if not exclude:
            included.append(page)

    print(f"Found {len(included)} relevant pages")
    return included


def get_title_block_bbox(page_wh: tuple, clip_wh: tuple) -> fitz.Rect:
    # A1 landscape = 2384 × 1684 pixels (web)
    # Page top left corner is (0,0). Incrementing x moves right, incrementing y moves down
    # Specifiy bounding box for title block as proporition of page width and height
    box_top_left = (page_wh[0] * clip_wh[0], page_wh[1] * clip_wh[1])
    box_bottom_right = page_wh
    rect = fitz.Rect(box_top_left, box_bottom_right)
    return rect


def extract_page_features(pages, img_paths) -> list[PageFeautres]:
    page_features = []
    for page in pages:
        text_features = []
        page_num = page.number + 1
        blocks = page.get_text("blocks")

        for block in blocks:
            feature = parse_block_as_text_feature(page_num, block)
            if feature:
                text_features.append(feature)

        page_features.append(
            PageFeautres(
                page=page_num, img_path=img_paths[page_num], text_features=text_features
            )
        )

    return page_features


# Pymupdf docs - https://pymupdf.readthedocs.io/en/latest/app1.html
def find_text_in_bbox(search_string, page, bbox) -> list[dict]:
    match_bboxes = page.search_for(search_string, clip=bbox)
    matches = []
    for bbox in match_bboxes:
        matches.append({"text": search_string, "coords": bbox})
    return matches


def pad_bbox(feature: tuple, padding: tuple[int, int, int, int]):
    (
        x0,
        y0,
        x1,
        y1,
    ) = feature[:4]

    left, top, right, bottom = padding

    bbox = fitz.Rect(x0 + left, y0 + top, x1 + right, y1 + bottom)
    return bbox


def get_nearby_text(page, block, padding) -> list:
    padded_box = pad_bbox(block[:4], padding)
    data = page.get_text("dict", clip=padded_box)
    lines = []
    for block_no, text_block in enumerate(data["blocks"]):
        if text_block["type"] != 0:  # text block only
            continue
        for line_no, line in enumerate(text_block["lines"]):
            text = "".join(span["text"] for span in line["spans"]).strip()

            if not text or len(text) < 4:
                continue

            lines.append(
                {
                    "text": text,
                    "bbox": tuple(line["bbox"]),
                    "block_no": block_no,
                    "line_no": line_no,
                }
            )
    return lines

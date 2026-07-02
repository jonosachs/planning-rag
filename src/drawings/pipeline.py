from src.drawings.schemas import PageFeautres
from src.drawings.ingest import (
    extract_pages,
    get_planning_relevant_pages,
    extract_page_features,
)
from src.drawings.clean import render_pages


EXCLUDED_DWGS = ["joinery", "wet", "door", "window", "detail", "demolition"]


def extract_drawing_data(pdf_path) -> list[PageFeautres]:
    print("Getting drawings data..")

    # Extract all pdf pages
    pages = extract_pages(pdf_path)

    # Get planning relevant pages using page titles
    relevant_pages = get_planning_relevant_pages(pages, EXCLUDED_DWGS)

    # Render dwg images for context
    img_paths = render_pages(relevant_pages)

    # Parse drawing features as structured objects
    page_features = extract_page_features(relevant_pages, img_paths)

    return page_features


if __name__ == "__main__":
    print(extract_drawing_data("assets/plans.pdf")[0])

from src.drawings.chunk import batch_chunk, chunk_page_features
from src.drawings.schemas import PageFeautres, PdfTextFeature


def make_feature(text, bbox=(0.0, 0.0, 10.0, 10.0), block_no=0):
    return PdfTextFeature(
        page=5,
        text=text,
        bbox=bbox,
        block_no=block_no,
        block_type=0,
    )


def test_chunk_page_features_creates_feature_chunks_with_drawing_metadata():
    page = PageFeautres(
        page=5,
        img_path="tmp/p5.png",
        text_features=[
            make_feature("setback 900mm from boundary", block_no=1),
        ],
    )

    chunks = chunk_page_features(page)

    assert len(chunks) == 2
    assert chunks[0].text.startswith("Drawing page 5. Feature type: setback.")
    assert chunks[0].metadata == {
        "source": "drawings",
        "chunk_kind": "feature",
        "page": 5,
        "img_path": "tmp/p5.png",
        "feature_type": "setback",
        "source_text": "setback 900mm from boundary",
        "bbox_x0": 0.0,
        "bbox_y0": 0.0,
        "bbox_x1": 10.0,
        "bbox_y1": 10.0,
        "block_no": 1,
        "block_type": 0,
        "chunk_index": 0,
    }


def test_chunk_page_features_adds_nearby_drawing_text():
    page = PageFeautres(
        page=5,
        img_path="tmp/p5.png",
        text_features=[
            make_feature("setback 900mm from boundary", bbox=(0, 100, 10, 110)),
            make_feature("title boundary 234 degrees", bbox=(20, 120, 40, 130)),
        ],
    )

    chunks = chunk_page_features(page)

    assert "Nearby drawing text: title boundary 234 degrees." in chunks[0].text


def test_batch_chunk_skips_pages_without_relevant_text_features():
    pages = [
        PageFeautres(page=1, img_path="tmp/p1.png", text_features=[]),
        PageFeautres(
            page=2,
            img_path="tmp/p2.png",
            text_features=[make_feature("private open space")],
        ),
    ]

    chunks = batch_chunk(pages)

    assert len(chunks) == 2
    assert all(chunk.metadata["source"] == "drawings" for chunk in chunks)

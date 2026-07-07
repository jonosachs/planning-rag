from src.drawings.service import DrawingsSource


def test_drawing_service():
    service = DrawingsSource(pdf_path="assets/plans.pdf")
    data = service.load()
    chunks = service.chunk(data)
    print(chunks[0])


if __name__ == "__main__":
    test_drawing_service()

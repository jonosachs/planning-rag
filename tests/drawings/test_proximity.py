from src.drawings.proximity import TextToken, classify_dimension_token


def token(text, x0, y0, x1=None, y1=None):
    return TextToken(
        page=1,
        text=text,
        bbox=(x0, y0, x1 or x0 + 10, y1 or y0 + 10),
    )


def test_classify_dimension_prefers_internal_label_when_closer_than_boundary():
    dimension = token("980", 100, 100)
    classified = classify_dimension_token(
        dimension,
        boundary_labels=[token("boundary", 500, 100)],
        building_labels=[token("wall", 520, 100)],
        internal_labels=[token("study", 110, 100)],
        service_labels=[],
    )

    assert classified.classification == "internal_dimension"
    assert classified.nearest_internal.text == "study"


def test_classify_dimension_prefers_courtyard_label_when_closer_than_boundary():
    dimension = token("2825", 100, 100)
    classified = classify_dimension_token(
        dimension,
        boundary_labels=[token("boundary", 420, 100)],
        building_labels=[token("wall", 440, 100)],
        internal_labels=[token("courtyard", 115, 100)],
        service_labels=[],
    )

    assert classified.classification == "open_space_or_courtyard_dimension"


def test_classify_dimension_as_possible_setback_near_boundary_and_wall():
    dimension = token("1030", 100, 100)
    classified = classify_dimension_token(
        dimension,
        boundary_labels=[token("boundary", 105, 100)],
        building_labels=[token("wall", 120, 100)],
        internal_labels=[token("study", 500, 100)],
        service_labels=[],
    )

    assert classified.classification == "possible_building_setback"

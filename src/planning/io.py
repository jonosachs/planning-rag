import json

DATA_PATH = "assets/port.json"
INCLUDED_TERMS = ["housing", "general", "heritage", "residential", "overlays"]


def get_clauses():
    with open(DATA_PATH) as f:
        data = json.load(f)

    clauses = data.get("clauses")
    # titles = [clause.get("title") for clause in clauses]

    selected = []

    for idx, c in enumerate(clauses):
        title = c.get("title")
        if any(word.strip() in INCLUDED_TERMS for word in title.lower().split()):
            selected.append(clauses[idx])

    for s in selected:
        print(s.get("title"))

    return selected


if __name__ == "__main__":
    get_clauses()

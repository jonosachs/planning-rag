from dataclasses import asdict
import json
from pathlib import Path


def write_json(data, file_path):
    path = Path(file_path)
    try:
        with open(path, "w") as f:
            json.dump([asdict(c) for c in data], f, indent=2)
    except IOError as e:
        print(f"❌ Error writing chunks to file: {e}")
    except TypeError as e:
        print(f"❌ Error writing chunks to file: {e}")

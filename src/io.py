from dataclasses import asdict
import json


def write_json(data, filename):
    try:
        with open(filename, "w") as f:
            json.dump([asdict(c) for c in data], f, indent=2)
    except IOError as e:
        print(f"❌ Error writing chunks to file: {e}")
    except TypeError as e:
        print(f"❌ Error writing chunks to file: {e}")

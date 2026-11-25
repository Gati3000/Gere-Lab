import json
import sys
from pathlib import Path


def main():
    target = Path(sys.argv[1])
    source = Path(sys.argv[2])
    seen = set()
    rows = []
    for path in (target, source):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line in seen:
                continue
            seen.add(line)
            try:
                key = str(json.loads(line).get("time", ""))
            except (ValueError, AttributeError):
                key = ""
            rows.append((key, line))
    rows.sort(key=lambda row: row[0])
    target.write_text("\n".join(line for _, line in rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

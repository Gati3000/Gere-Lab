import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from Manifest import PACKAGES

STEPS = [
    ["apt-get", "update", "-qq"],
    ["apt-get", "upgrade", "-y", "-qq"],
    ["apt-get", "install", "-y", "-qq", *PACKAGES],
]


def main():
    env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
    for step in STEPS:
        print("  " + " ".join(step[:2]), flush=True)
        if subprocess.run(step, env=env).returncode != 0:
            print("  Update failed: " + " ".join(step), flush=True)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

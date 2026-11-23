#!/usr/bin/env python3
"""Launcher Gere-Lab: uruchamiany ręcznie raz, po skopiowaniu repo.

Powitanie, brakujące pakiety, pytanie o Gere-Drive i kolory terminala
(Maintenance/Setup.sh), potem rejestracja komendy "Lab" (Maintenance/Install.sh).
Tylko biblioteka standardowa, żeby działał też przed instalacją python3-yaml.
"""
import subprocess
import sys
from pathlib import Path

MAINT = Path(__file__).resolve().parent.parent / "Maintenance"
SETUP = MAINT / "Setup.sh"
INSTALL = MAINT / "Install.sh"


def run(script, *args):
    if not script.is_file():
        sys.exit(f"Brak pliku: {script}")
    return subprocess.run(["bash", str(script), *args]).returncode


def main():
    if "--banner" in sys.argv[1:]:
        sys.exit(run(SETUP, "banner"))
    if not sys.stdin.isatty():
        sys.exit("Launcher wymaga terminala.")
    if run(SETUP) != 0:
        sys.exit("Konfiguracja nie została ukończona. Uruchom Launcher ponownie.")
    if run(INSTALL) != 0:
        sys.exit("Nie udało się zarejestrować komendy Lab.")
    print("Gotowe. Uruchom program: Lab start")


if __name__ == "__main__":
    main()

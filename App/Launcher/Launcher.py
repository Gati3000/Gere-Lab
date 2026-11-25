#!/usr/bin/env python3
"""Launcher Gere-Lab: jedyny skrypt pierwszego uruchomienia.

Baner, pakiety, Gere-Drive, katalogi, prompt, komenda "Lab", aktualizacje.
  python3 Launcher.py            pełna konfiguracja
  python3 Launcher.py --banner   tylko ekran powitalny
Do testów: HOME, GERE_DRIVE_DIR, GERE_BIN_DIR (gdzie zrobić symlink Lab).
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
LAB = REPO / "App" / "Maintenance" / "Lab"
BIN_DIR = Path(os.environ.get("GERE_BIN_DIR") or "/usr/local/bin")
DRIVE_DIR = Path(os.environ.get("GERE_DRIVE_DIR") or REPO.parent / "Gere-Drive")
DRIVE_URL = "https://github.com/Gati3000/Gere-Drive.git"
DRIVE_BRANCH = "main"
MARK = Path.home() / ".config" / "gere-lab" / "first-run-done"

BLUE, CYAN, GREEN = "\033[34m", "\033[96m", "\033[32m"
WHITE, RED, RESET = "\033[97m", "\033[31m", "\033[0m"
LOGO = r'''   ________________  ______   __    ___    ____ 
  / ____/ ____/ __ \/ ____/  / /   /   |  / __ )
 / / __/ __/ / /_/ / __/    / /   / /| | / __  |
/ /_/ / /___/ _, _/ /___   / /___/ ___ |/ /_/ / 
\____/_____/_/ |_/_____/  /_____/_/  |_/_____/  '''
PS1_LINE = r"PS1='\[\e[96m\]\u\[\e[34m\]@\[\e[96m\]\h\[\e[0m\]:\w\$ '"
PROMPT_BLOCK = f"# >>> Gere-Lab prompt >>>\n{PS1_LINE}\n# <<< Gere-Lab prompt <<<\n"


def _frames():
    enc = (sys.stdout.encoding or "").lower()
    return "⠷⠯⠟⠻⠽⠾" if "utf" in enc and os.environ.get("TERM") != "linux" else "|/-\\"


FRAMES = _frames()


def banner():
    sys.stdout.write("\033[2J\033[3J\033[H")
    print(BLUE + LOGO + RESET)
    print(CYAN + "\n  Welcome to Gere Lab" + RESET + "\n")


def spinner(label, work, erase=False):
    out = {}

    def target():
        try:
            out["r"] = work()
        except Exception as e:
            out["e"] = e

    t = threading.Thread(target=target)
    t.start()
    i = 0
    sys.stdout.write("\033[?25l")
    try:
        while t.is_alive():
            sys.stdout.write(f"\r  {label} {FRAMES[i % len(FRAMES)]}")
            sys.stdout.flush()
            i += 1
            time.sleep(0.12)
        t.join()
    finally:
        if erase:
            sys.stdout.write("\r\033[K\033[?25h")
        else:
            sys.stdout.write(f"\r\033[K  {label}\033[?25h\n")
        sys.stdout.flush()
    if "e" in out:
        raise out["e"]
    return out.get("r")


def ask(question):
    try:
        a = input(f"\n  {question} [y/N] ").strip().lower()
    except EOFError:
        a = ""
    return a in ("y", "yes", "t", "tak")


def ok(text="Done"):
    print("  " + GREEN + text + RESET)


def fail(msg):
    print(f"  {RED}Failed{RESET}\n  {msg}")
    return False


def run(cmd, **kw):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", DEBIAN_FRONTEND="noninteractive")
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, **kw)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"{cmd[0]} failed")
    return r.stdout


def check_packages():
    def work():
        time.sleep(0.7)
        missing = []
        if not shutil.which("git"):
            missing.append("git")
        if importlib.util.find_spec("yaml") is None:
            missing.append("python3-yaml")
        return missing

    missing = spinner("Checking packages", work)
    if not missing:
        ok("Everything is installed")
        return True

    def install():
        run(["apt-get", "update", "-qq"])
        run(["apt-get", "install", "-y", "-qq", *missing])

    try:
        spinner("Installing " + ", ".join(missing), install)
    except Exception as e:
        return fail(e)
    ok()
    return True


def setup_drive():
    if (DRIVE_DIR / ".git").is_dir():
        print(f"\n  {GREEN}Gere-Drive is already installed{RESET}")
        return True
    if not ask("Do you want to install additional tool Gere-Drive?"):
        return True
    if DRIVE_DIR.exists() and any(DRIVE_DIR.iterdir()):
        print(f"  {RED}{DRIVE_DIR} is not empty and is not a git repository{RESET}")
        return False
    print()
    try:
        spinner("Cloning Gere-Drive", lambda: run(
            ["git", "clone", "--branch", DRIVE_BRANCH, DRIVE_URL, str(DRIVE_DIR)]))
    except Exception as e:
        return fail(e)
    ok()
    return True


def set_prompt():
    rc = Path.home() / ".bashrc"
    text = rc.read_text() if rc.exists() else ""
    text = re.sub(r"# >>> Gere-Lab prompt >>>.*?# <<< Gere-Lab prompt <<<\n?",
                  "", text, flags=re.S)
    if text and not text.endswith("\n"):
        text += "\n"
    rc.write_text(text + PROMPT_BLOCK)


def register_lab():
    """Komenda Lab: symlink w BIN_DIR do App/Maintenance/Lab."""
    try:
        LAB.chmod(LAB.stat().st_mode | 0o111)
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        link = BIN_DIR / "Lab"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(LAB)
    except OSError as e:
        return fail(f"Could not register the Lab command: {e}")
    return True


def find_update():
    """(gałąź, liczba nowych commitów) albo None."""
    try:
        def g(*a):
            return run(["git", "-C", str(REPO), *a], timeout=20).strip()
        branch = g("rev-parse", "--abbrev-ref", "HEAD")
        if not branch or branch == "HEAD":
            return None
        g("fetch", "--quiet", "origin", branch)
        n = g("rev-list", "--count", f"HEAD..origin/{branch}")
        return (branch, int(n)) if n.isdigit() and int(n) > 0 else None
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        return None


def check_updates():
    found = spinner("Checking for updates", find_update, erase=True)
    if not found:
        return
    branch, n = found
    print(f"  {GREEN}Update available{RESET} ({branch}, {n} new)")
    args = {"Main": ["update"], "Beta": ["update", "-b"]}.get(branch)
    if args is None:
        print(f"  Branch {branch} is not supported by Lab update.")
        return
    if not ask("Update now?"):
        print("  Later: Lab " + " ".join(args))
        return
    print()
    if subprocess.run(["bash", str(LAB), *args]).returncode != 0:
        print(f"  {RED}Update failed. Try: Lab {' '.join(args)}{RESET}")


def main():
    if "--banner" in sys.argv[1:]:
        banner()
        return 0
    if not sys.stdin.isatty():
        sys.exit("Launcher requires a terminal.")
    if not LAB.is_file():
        sys.exit(f"Missing file: {LAB}")

    banner()
    if not check_packages() or not setup_drive():
        return 1
    for d in ("Messeges", "Parts"):
        (REPO / "Database" / d).mkdir(parents=True, exist_ok=True)
    set_prompt()
    if not register_lab():
        return 1
    subprocess.run([sys.executable, str(REPO / "App" / "Maintenance" / "Update.py")])
    MARK.parent.mkdir(parents=True, exist_ok=True)
    MARK.touch()
    check_updates()
    print(f"\n  {GREEN}Gere Lab is set up.{RESET}")
    print(f"  {WHITE}Run program with command Lab start{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

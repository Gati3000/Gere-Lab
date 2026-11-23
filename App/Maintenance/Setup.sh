#!/usr/bin/env bash
# Pierwsze uruchomienie Gere-Lab: powitanie, potrzebne pakiety, Gere-Drive, kolory terminala.
# Odpala się samo przy pierwszym "Lab start". Ręcznie: Lab setup

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
MAINT_DIR="$(dirname "$SCRIPT_PATH")"
REPO_DIR="$(dirname "$(dirname "$MAINT_DIR")")"
DRIVE_DIR="${GERE_DRIVE_DIR:-$(dirname "$REPO_DIR")/Gere-Drive}"
DRIVE_URL="https://github.com/Gati3000/Gere-Drive.git"
DRIVE_BRANCH="main"
MARK_DIR="$HOME/.config/gere-lab"
MARK="$MARK_DIR/first-run-done"

CYAN=$'\e[96m'
DIM=$'\e[2m'
NONE=$'\e[0m'

banner() {
    printf '%s' "$CYAN"
    cat <<'ART'
   ________________  ______   __    ___    ____ 
  / ____/ ____/ __ \/ ____/  / /   /   |  / __ )
 / / __/ __/ / /_/ / __/    / /   / /| | / __  |
/ /_/ / /___/ _, _/ /___   / /___/ ___ |/ /_/ / 
\____/_____/_/ |_/_____/  /_____/_/  |_/_____/  
ART
    printf '\n  Welcome to Gere Lab\n%s\n' "$NONE"
    local lines=(
        "Od wiadomości na WhatsAppie do etykiety na paczce."
        "VIN sprawdzony, część znaleziona, paczka gotowa."
        "Mniej klikania, więcej wysyłek."
    )
    printf '  %s%s%s\n\n' "$DIM" "${lines[RANDOM % ${#lines[@]}]}" "$NONE"
}

install_deps() {
    echo "Sprawdzam potrzebne pakiety..."
    local missing=()
    command -v git >/dev/null || missing+=(git)
    command -v python3 >/dev/null || missing+=(python3)
    python3 -c 'import yaml' 2>/dev/null || missing+=(python3-yaml)
    if [[ ${#missing[@]} -eq 0 ]]; then
        echo "  Wszystko jest zainstalowane."
        return 0
    fi
    echo "  Instaluję: ${missing[*]}"
    apt-get update -qq && apt-get install -y -qq "${missing[@]}" || {
        echo "Błąd: nie udało się zainstalować pakietów." >&2
        return 1
    }
}

setup_drive() {
    if [[ -d "$DRIVE_DIR/.git" ]]; then
        echo "Gere-Drive jest już pobrane ($DRIVE_DIR)."
        return 0
    fi
    local answer
    read -r -p "Pobrać Gere-Drive? (y + Enter = tak, samo Enter = nie): " answer
    if [[ "$answer" =~ ^([yY]|[yY][eE][sS])$ ]]; then
        if [[ -n "$(ls -A "$DRIVE_DIR" 2>/dev/null)" ]]; then
            echo "Błąd: $DRIVE_DIR istnieje, nie jest puste i nie jest repozytorium git." >&2
            return 1
        fi
        git clone --branch "$DRIVE_BRANCH" "$DRIVE_URL" "$DRIVE_DIR" || {
            echo "Błąd: nie udało się pobrać Gere-Drive. Spróbuj ponownie: Lab setup" >&2
            return 1
        }
    else
        mkdir -p "$REPO_DIR/Database/Messeges" "$REPO_DIR/Database/Parts"
        echo "Utworzono Database/Messeges i Database/Parts w Gere-Lab."
    fi
}

set_prompt() {
    local rc="$HOME/.bashrc"
    touch "$rc"
    sed -i '/# >>> Gere-Lab prompt >>>/,/# <<< Gere-Lab prompt <<</d' "$rc"
    cat >> "$rc" <<'PROMPT'
# >>> Gere-Lab prompt >>>
PS1='\[\e[96m\]\u\[\e[34m\]@\[\e[96m\]\h\[\e[0m\]:\w\$ '
# <<< Gere-Lab prompt <<<
PROMPT
    echo "Kolory terminala zapisane w $rc (nowy terminal albo: source ~/.bashrc)."
}

main() {
    if [[ ! -t 0 ]]; then
        echo "Setup wymaga terminala." >&2
        exit 1
    fi
    banner
    install_deps || exit 1
    setup_drive || exit 1
    set_prompt
    mkdir -p "$MARK_DIR" && touch "$MARK"
    echo "Gotowe."
}

if [[ "${1:-}" == "banner" ]]; then banner; else main "$@"; fi

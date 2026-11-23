#!/usr/bin/env bash
# Rejestruje komendę "Lab" w systemie (symlink do /usr/local/bin)
set -e
DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
chmod +x "$DIR/Lab"
ln -sf "$DIR/Lab" /usr/local/bin/Lab
echo "Zainstalowano. Użyj: Lab start | Lab stop"

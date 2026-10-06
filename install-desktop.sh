#!/usr/bin/env bash
# Add the existing installation to the current user's KDE application menu.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if (( $# > 1 )); then
	printf 'Usage: %s [path/to/why-here]\n' "$0" >&2
	exit 1
fi
executable=${1:-}
if [[ -z "$executable" ]]; then
	for candidate in "$root/why-here" "$root/.venv/bin/why-here" "$root/dist/why-here"; do
		if [[ -f "$candidate" && -x "$candidate" ]]; then
			executable=$candidate
			break
		fi
	done
fi
if [[ ! -f "$executable" || ! -x "$executable" ]]; then
	printf 'Executable not found. Usage: %s /absolute/path/to/why-here\n' "$0" >&2
	exit 1
fi
executable=$(realpath -- "$executable")
# Escape Exec quoting first, then desktop-entry string escaping.
executable=${executable//\\/\\\\}
executable=${executable//\"/\\\"}
executable=${executable//\$/\\\$}
executable=${executable//\`/\\\`}
executable=${executable//%/%%}
executable=${executable//\\/\\\\}
executable=${executable//$'\n'/\\n}
executable=${executable//$'\r'/\\r}
executable=${executable//$'\t'/\\t}

applications="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p -- "$applications"
desktop="$applications/org.local.WhyHere.desktop"
cat > "$desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Why am I here?
Name[ru]=Зачем я здесь?
Comment=Purpose and time limits for applications
Comment[ru]=Цели и ограничения времени для приложений
Exec=/usr/bin/env -- "$executable" --show
Icon=appointment-soon
Terminal=false
Categories=Utility;
EOF

if command -v kbuildsycoca6 >/dev/null 2>&1; then
	kbuildsycoca6 --noincremental || printf 'KDE menu refresh failed; log in again to refresh it.\n' >&2
fi
printf 'Installed: %s\n' "$desktop"

#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tex=${LUALATEX:-/Library/TeX/texbin/lualatex}
for project in "Project One" "Project Two"; do
  directory="$root/build/fixtures/$project"
  mkdir -p "$directory"
  cp "$root/support/fixtures/$project/main.tex" "$directory/main.tex"
  (cd "$directory" && "$tex" -interaction=nonstopmode -halt-on-error -synctex=1 main.tex >/dev/null)
done
printf '%s\n' "$root/build/fixtures"

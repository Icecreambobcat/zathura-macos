#!/bin/sh
# Build pinned editable components without installing into the Homebrew prefix.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
brew=${HOMEBREW_BREW_FILE:-/opt/homebrew/bin/brew}
prefix=$("$brew" --prefix)
stage="$root/stage/dev"
export PATH="$prefix/bin:$prefix/opt/gettext/bin:$PATH"
export PKG_CONFIG_PATH="$stage/lib/pkgconfig:$prefix/opt/sqlite/lib/pkgconfig:$prefix/opt/zlib/lib/pkgconfig:$prefix/opt/libarchive/lib/pkgconfig:$prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"

build() {
  name=$1
  shift
  directory="$root/build/dev/$name"
  if [ -f "$directory/build.ninja" ]; then
    meson setup --reconfigure "$directory" "$root/src/$name" --prefix="$stage" --libdir=lib "$@"
  else
    meson setup "$directory" "$root/src/$name" --prefix="$stage" --libdir=lib "$@"
  fi
  meson compile -C "$directory"
  meson install -C "$directory"
}

build synctex
build girara -Ddocs=disabled
build zathura -Dsynctex=enabled -Dseccomp=disabled -Dlandlock=disabled \
  -Dmanpages=disabled -Dshell-completions=disabled -Dconvert-icon=disabled \
  -Dtests-x11=disabled -Dtests-wayland=disabled
for plugin in zathura-pdf-mupdf zathura-djvu zathura-ps zathura-cb; do
  build "$plugin" "-Dplugindir=$stage/lib/zathura"
done
python3 "$root/support/test-synctex-metadata.py" --prefix "$stage"
meson test -C "$root/build/dev/zathura" --print-errorlogs
printf '\nBuilt editable sources into %s\n' "$stage"

# Zathura on macOS

Development workspace for the native multi-window viewer and its Homebrew packages.
The installable app lives in [icecreambobcat/personal](https://github.com/Icecreambobcat/homebrew-personal).
It uses Homebrew libraries and is not a standalone app bundle.

## Sources

Clone with submodules:

```sh
git clone --recurse-submodules https://github.com/Icecreambobcat/zathura-macos.git
cd zathura-macos
```

`src/` contains seven pinned Git submodules. Zathura, SyncTeX and the MuPDF plugin
use the forks' `macos` branches; Girara and the other plugins use upstream commits.
The submodule gitlinks are the source pins; there is no second lock manifest to
keep in sync. `packaging/homebrew-personal` is the editable tap checkout. Updating
a source branch does not update an installed package: the tap must pin the new
archive and checksum.

## Build editable sources

`Brewfile` is the single declaration of third-party development tools and libraries.
Check or install missing packages into the normal Homebrew prefix:

```sh
brew bundle check --file=Brewfile
brew bundle install --file=Brewfile
```
The [dependency notes](support/DEPENDENCIES.md) explain the staging boundary.

```sh
sh support/build-dev.sh
python3 support/make-native-app.py
open -a "$PWD/build/dev/Zathura Dev.app"
```

The build script compiles all seven components into `build/dev/`, stages them under
`stage/dev/`, checks SyncTeX metadata and runs the native Zathura tests. It does not
install or upgrade Homebrew packages. Set `HOMEBREW_BREW_FILE` when Homebrew is not at
`/opt/homebrew/bin/brew`.

The bundle assembler reads assets from `packaging/homebrew-personal` and uses the
Brewfile's Python, GLib and D-Bus executables. The development app has a separate
bundle identifier and `/tmp/zathura-dev-<uid>/bus`. It uses normal personal settings
unless configuration directories are supplied explicitly. No editor callback is
injected. There are no legacy launchers or extracted dependency trees.

## Runtime design

One regular native app process owns independent document windows. Each window owns
its settings, page state, SyncTeX scanner, editor callback and D-Bus endpoint.
Reopening an existing document presents its window. `q` and Cmd-W close a window;
Cmd-Q quits the app. Closing the final window ends the process.

The native executable stays the bundle entry point. A synchronous helper prepares
the private bus and environment without replacing the viewer PID. The macOS surface
size handler retains the mapped native size after an accessibility resize, rather
than restoring GTK's stale default size over yabai's layout.

VimTeX's `zathura_simple` viewer routes forward search by filename. Reverse callbacks
remain configurable through `zathurarc`, `-x` or `ZATHURA_SYNCTEX_EDITOR`. Packaging
does not edit dotfiles or change default file handlers.

## Tests

`support/test-macos-host.py` exercises a dedicated idle app/bus pair with temporary
settings. It refuses to reuse an occupied document bus. Run `sh
support/make-test-fixtures.sh` to build its two-page PDF/TeX/SyncTeX fixtures from
tracked source. LuaLaTeX is required for this optional test step.

```sh
python3 support/test-macos-host.py \
  --app "$PWD/build/dev/Zathura Dev.app" \
  --bus "unix:path=/tmp/zathura-dev-$(id -u)/bus" \
  --fixtures "$PWD/build/fixtures" \
  --report "$PWD/build/reports/dev-regression.json"
```

The app starts its private bus if needed. The test opens visible windows and toggles
their yabai float state. It
checks native PID reuse, Launch Services multi-file opens, independent page state,
filename-routed forward SyncTeX, eight float/retile cycles, six neighbour open/close
cycles, stdin cleanup and independent close/final exit. Reports stay under `build/`.

The native `test_multiwindow` suite also accepts `ZATHURA_TEST_PLUGINS`,
`ZATHURA_TEST_PDF_ONE` and `ZATHURA_TEST_PDF_TWO`. Supplying real SyncTeX fixtures
enables its document and inverse-callback test; without them that case is skipped.
ASan/UBSan can be enabled in a separate Meson build using
`-Db_sanitize=address,undefined -Db_lundef=false`.

Source and installed revision-8 runtime regressions passed locally, along with the
native sanitizer tests, staged component builds, metadata checks, Girara tests and
Homebrew type/style/audit/formula/linkage/signature checks. Physical Ctrl-clicks in
both installed-app PDFs reached two separate VimTeX editors at the correct source
and line (3:1), using `support/test-vimtex.vim` and a test-local cache. AppKit confirmed
one regular native application, and Launch Services listed the installed app as a
PDF opener candidate without changing defaults. Intel runtime behaviour, reboot
recovery and reconnecting an already-running viewer after its bus dies require
separate verification.

## Packaging and bottles

The tap consumes immutable fork archives, not patches copied from this checkout.
On this machine, Homebrew's installation tap is a real Git worktree sharing the
packaging submodule's history. This retains Homebrew's normal tap identity in child
processes; a symlinked tap does not. Edit packaging in the workspace branch, then
fast-forward the installation worktree to the tested/published commit. The second
checkout contains formula metadata and assets, not copied dependency libraries.
Fresh clones can use a normal `brew tap icecreambobcat/personal` for installation.
If moving this workspace, repair the linked worktree paths with `git worktree repair`.
When changing the core, bump both `zathura-core` and `zathura`: the app contains a copy
of the core executable. Rebuild all plugins if the plugin ABI changes.

Zathura-related pull requests and manual runs build the full seven-formula stack.
The Apple Silicon job requires all seven bottles. Intel jobs may skip builds when
dependencies lack compatible bottles; a green job alone does not verify them.
The `pr-pull` workflow merges tested pull requests and publishes bottles.
Direct source pushes alone do not publish bottles.

For a fresh local bottle build, use `brew install --build-bottle <formula>` followed
by `brew bottle --json <formula>`. Current Homebrew does not accept `--build-bottle`
on `brew reinstall`. Do not relabel a bottle built on a newer macOS as an older OS,
or force a newer CPU baseline to make local builds faster.

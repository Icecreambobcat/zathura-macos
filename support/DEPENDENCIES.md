# Development dependencies

`Brewfile` declares the third-party tools and libraries used by the development
build. Homebrew owns their versions, Cellar installations, downloads and runtime
closure. There are no extracted dependency bottles or copied library trees in this
workspace. Source components are pinned by Git submodule commits.

Check or install missing development packages from the workspace root:

```sh
brew bundle check --file=Brewfile
brew bundle install --file=Brewfile
```

Installation uses the normal shared Homebrew prefix. Do not use `--global` or
`brew bundle cleanup` for this workspace. A Brewfile is not an isolated Homebrew
installation, and it does not freeze third-party package versions.

`sh support/build-dev.sh` compiles the seven editable components under `build/dev/`
and installs only those outputs into `stage/dev/`. Its `PKG_CONFIG_PATH` prefers
that stage, then the required Homebrew keg-only metadata directories. Environment
changes apply only to the script and its children. It never installs or upgrades
Homebrew packages.

`python3 support/make-native-app.py` assembles `build/dev/Zathura Dev.app` from that
stage and the packaging submodule's assets. Python, GLib and D-Bus executables come
from Homebrew. The installed app uses the same packaging assets but the formulae's
immutable source archives and Homebrew-managed dependency graph.

The two-page SyncTeX fixtures are tracked as TeX source under `support/fixtures/`.
Run `sh support/make-test-fixtures.sh` to compile them under `build/fixtures/` using
LuaLaTeX. TeX is an optional test tool, not a viewer runtime dependency.

Keep generated files under `build/` and `stage/`; both are ignored. `build/reports/`
contains acceptance evidence, while `build/bottles/` contains unpublished local
bottle artifacts. Neither directory is a source of editable application code.

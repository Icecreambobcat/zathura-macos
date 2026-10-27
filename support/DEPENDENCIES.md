# Project dependencies

`Brewfile` is this workspace's package inventory. `support/components.lock.json`
records exact source commits and an observed snapshot of direct dependency versions.
The Homebrew versions in that snapshot are not enforced installation pins.

## Fetching

Run from any directory:

```sh
python3 /path/to/this/workspace/support/fetch-dependencies.py
```

The helper downloads packages only. It reads the project Brewfile, resolves runtime
dependencies, and does not install or upgrade packages, start services, change shell
configuration, or edit a global Brewfile. Its cache, logs and temporary files stay
under `.cache/` and `logs/` in this workspace. Environment changes apply only to the
helper's child processes.

After a successful fetch, `.cache/dependencies.json` records the downloaded archive
paths, versions and SHA-256 hashes. This generated inventory is intentionally ignored
by Git. A dry run is available with `--dry-run`; it may still cache package metadata.

`--reuse-cache /path/to/an/existing/Homebrew/cache` seeds matching completed archives
using hard links where possible, falling back to copies. It does not alter or remove
files from the source cache. Homebrew verifies the fetched packages afterwards.

The initial fetch used Homebrew's normal shared cache. Those files are deliberately
left alone because the cache may be shared with other projects. Nothing was installed
by that fetch. Subsequent helper runs use the workspace cache.

## Installation boundary

A Brewfile is not an isolated Homebrew installation. Running `brew bundle install`
would use the normal shared Homebrew prefix. No such installation has been performed.
Do not use `--global` or `brew bundle cleanup` for this project.

Keep future source-build output under `build/` and install development artefacts into
`stage/`. A fully private dependency prefix, if wanted, requires a separate build
plan; the local download cache does not provide that isolation.

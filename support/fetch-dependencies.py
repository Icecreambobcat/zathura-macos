#!/usr/bin/env python3
"""Fetch the Brewfile's packages into this workspace without installing them."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def unique_lines(output):
    return list(dict.fromkeys(line.strip() for line in output.splitlines() if line.strip()))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show the package plan without fetching package archives.")
    parser.add_argument("--reuse-cache", type=Path, help="Seed completed package archives from an existing cache without modifying it.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    cache = root / ".cache" / "homebrew"
    logs = root / "logs" / "homebrew"
    temporary = root / ".cache" / "homebrew-tmp"
    brewfile = root / "Brewfile"
    brew = shutil.which("brew")
    if brew is None:
        raise SystemExit("Homebrew is not available; no installation was attempted.")

    env = os.environ.copy()
    env.update({
        "HOMEBREW_CACHE": str(cache),
        "HOMEBREW_LOGS": str(logs),
        "HOMEBREW_TEMP": str(temporary),
        "HOMEBREW_NO_AUTO_UPDATE": "1",
        "HOMEBREW_NO_INSTALL_CLEANUP": "1",
        "HOMEBREW_NO_ANALYTICS": "1",
    })
    for directory in (cache, logs, temporary):
        directory.mkdir(parents=True, exist_ok=True)

    def output(*arguments):
        return subprocess.check_output([brew, *arguments], cwd=root, env=env, text=True)

    actual_cache = Path(output("--cache").strip()).resolve()
    if actual_cache != cache.resolve():
        raise SystemExit("Homebrew did not select the workspace cache; refusing to fetch.")

    roots = unique_lines(output("bundle", "list", "--formula", "--file", str(brewfile)))
    if not roots:
        raise SystemExit("The project Brewfile contains no formulae.")
    runtime_dependencies = unique_lines(output("deps", "--union", "--formula", *roots))
    packages = list(dict.fromkeys(roots + runtime_dependencies))
    print("Project dependencies: " + ", ".join(roots), flush=True)
    print("Package cache: " + str(cache), flush=True)
    print("Fetch plan (package roots plus runtime dependencies): " + ", ".join(packages), flush=True)
    if args.dry_run:
        return

    paths = [Path(line) for line in unique_lines(output("--cache", "--formula", *packages))]
    if len(paths) != len(packages):
        raise SystemExit("Unexpected cache-path output; refusing to seed or fetch archives.")
    for path in paths:
        path.relative_to(cache)

    seeded = 0
    if args.reuse_cache:
        source_cache = args.reuse_cache.expanduser().resolve(strict=True)
        if source_cache != cache.resolve():
            for destination in paths:
                source = source_cache / destination.relative_to(cache)
                if destination.exists() or not source.is_file() or source.is_symlink():
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(source, destination)
                except FileExistsError:
                    continue
                except OSError:
                    with source.open("rb") as source_stream, destination.open("xb") as destination_stream:
                        shutil.copyfileobj(source_stream, destination_stream)
                seeded += 1
    print("Reused completed archives: " + str(seeded), flush=True)

    # Resolve the runtime closure above instead of using fetch --deps, which
    # also fetched tools for rebuilding packaged libraries in the initial run.
    # This command only downloads: it does not install, upgrade or start services.
    subprocess.run([brew, "fetch", "--formula", *packages], cwd=root, env=env, check=True)

    info = json.loads(output("info", "--formula", "--json=v2", *packages))
    metadata = {item["name"]: item for item in info["formulae"]}
    archives = []
    for package, path in zip(packages, paths):
        if not path.is_file():
            raise SystemExit("Expected package archive is missing: " + str(path))
        item = metadata.get(package) or metadata[package.rsplit("/", 1)[-1]]
        archives.append({
            "name": package,
            "version": item["versions"]["stable"],
            "revision": item["revision"],
            "archive": str(path.relative_to(root)),
            "sha256": sha256(path),
        })
    inventory = {
        "state": "downloaded-not-installed",
        "brewfile": "Brewfile",
        "direct_dependencies": roots,
        "cache": str(cache.relative_to(root)),
        "packages": archives,
    }
    inventory_path = root / ".cache" / "dependencies.json"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=inventory_path.parent, delete=False) as stream:
        json.dump(inventory, stream, indent=2)
        stream.write("\n")
        temporary_path = Path(stream.name)
    os.replace(temporary_path, inventory_path)
    print("Verified package inventory: " + str(inventory_path), flush=True)
    print("Finished fetching. No packages were installed or upgraded; no services were started.", flush=True)


if __name__ == "__main__":
    main()

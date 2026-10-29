#!/usr/bin/env python3
"""Check an isolated SyncTeX installation's pkg-config metadata and headers."""

import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", required=True, type=Path)
    parser.add_argument("--libdir", default="lib")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    prefix = args.prefix.resolve()
    pcdir = prefix / args.libdir / "pkgconfig"
    pkgconf = shutil.which("pkgconf") or shutil.which("pkg-config")
    if not pkgconf:
        raise SystemExit("pkgconf or pkg-config is required; nothing was installed.")
    env = os.environ.copy()
    env["PKG_CONFIG_PATH"] = str(pcdir) + os.pathsep + env.get("PKG_CONFIG_PATH", "")

    def query(*options):
        return subprocess.check_output([pkgconf, *options, "synctex"], env=env, text=True).strip()

    failures = []

    def check(condition, description):
        print(("PASS: " if condition else "FAIL: ") + description, flush=True)
        if not condition:
            failures.append(description)

    check(Path(query("--variable=pcfiledir")).resolve() == pcdir, "Use the requested installation's synctex.pc")
    expected = (root / "src/synctex/synctex_parser_api_level.txt").read_text().strip()
    check(query("--modversion") == expected, "Advertise the upstream API level " + expected)
    minimum = subprocess.run([pkgconf, "--atleast-version=2", "synctex"], env=env).returncode
    check(minimum == 0, "Satisfy Zathura's synctex >= 2 requirement")
    flags = shlex.split(query("--cflags", "--libs"))
    check("-I" + str(prefix / "include") in flags, "Export the include root for namespaced headers")
    check("-L" + str(prefix / args.libdir) in flags, "Export the installed library directory")
    static_flags = shlex.split(query("--static", "--libs"))
    check("-lz" in static_flags, "Expose the private zlib dependency for static consumers")

    fixture_root = root / "build" / "fixtures" / "metadata"
    fixture_root.mkdir(parents=True, exist_ok=True)
    compiler = shlex.split(env.get("CC", "cc"))
    with tempfile.TemporaryDirectory(prefix="synctex-", dir=fixture_root) as directory:
        directory = Path(directory)
        for name, header in [("namespaced", "synctex/synctex_parser.h"), ("legacy", "synctex_parser.h")]:
            check((prefix / "include" / header).is_file(), "Install the " + name + " header layout")
            source = directory / (name + ".c")
            executable = directory / name
            source.write_text(
                "#include <stddef.h>\n#include <" + header + ">\n"
                "int main(void) {\n"
                "  synctex_scanner_p scanner = synctex_scanner_new_with_output_file(\"missing-metadata-test.pdf\", NULL, 0);\n"
                "  if (scanner != NULL) synctex_scanner_free(scanner);\n"
                "  return 0;\n}\n"
            )
            result = subprocess.run(
                [*compiler, str(source), "-o", str(executable), *flags, "-Wl,-rpath," + str(prefix / args.libdir)],
                cwd=directory, env=env, text=True, capture_output=True,
            )
            check(result.returncode == 0, "Compile and link a " + name + " header consumer using pkg-config flags")
            if result.returncode:
                print(result.stderr, flush=True)
                continue
            result = subprocess.run([str(executable)], cwd=directory, env=env, text=True, capture_output=True)
            check(result.returncode == 0, "Run the " + name + " consumer against the staged library")
            if result.returncode:
                print(result.stderr, flush=True)
    if failures:
        raise SystemExit(str(len(failures)) + " metadata checks failed")
    print("All SyncTeX metadata checks passed.", flush=True)


if __name__ == "__main__":
    main()

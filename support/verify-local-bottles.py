#!/usr/bin/env python3
"""Pour seven local bottles by formula name; restore temporary metadata even on failure."""
import functools
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

bottles = Path(sys.argv[1]).resolve()
tap = Path(subprocess.check_output(["brew", "--repository", "icecreambobcat/personal"], text=True).strip())
names = ["synctex", "zathura-core", "zathura-pdf-mupdf", "zathura-djvu", "zathura-ps", "zathura-cb", "zathura"]
originals = {tap / f"Formula/{name}.rb": (tap / f"Formula/{name}.rb").read_bytes() for name in names}
env = dict(os.environ, HOMEBREW_NO_AUTO_UPDATE="1", HOMEBREW_NO_INSTALL_CLEANUP="1",
           HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK="1")
def run(*args):
    subprocess.run([str(a) for a in args], env=env, check=True)
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(bottles))
server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
aliases = []
metadata_directory = tempfile.TemporaryDirectory(prefix="zathura-bottle-metadata-")
try:
    metadata = []
    for name in names:
        matches = list(bottles.glob(f"{name}--*.bottle.json"))
        assert len(matches) == 1, (name, matches)
        data = json.loads(matches[0].read_text())
        for item in data.values():
            item["bottle"]["root_url"] = f"http://127.0.0.1:{server.server_port}"
        local_metadata = Path(metadata_directory.name) / matches[0].name
        local_metadata.write_text(json.dumps(data))
        metadata.append(local_metadata)
        for item in data.values():
            for tag in item["bottle"]["tags"].values():
                alias = bottles / tag["filename"]
                if not alias.exists():
                    alias.symlink_to(tag["local_filename"])
                    aliases.append(alias)
    run("brew", "bottle", "--merge", "--write", "--no-commit", *metadata)
    for name in names:
        formula = f"icecreambobcat/personal/{name}"
        run("brew", "reinstall", "--force-bottle", formula)
        # Reinstall can preserve the source install\'s build-bottle mode and skip these steps.
        run("brew", "postinstall", formula)
        details = json.loads(subprocess.check_output(["brew", "info", "--json=v2", formula], text=True))["formulae"][0]
        version = details["versions"]["stable"] + (f'_{details["revision"]}' if details["revision"] else "")
        receipt = next(i for i in details["installed"] if i["version"] == version)
        assert receipt["poured_from_bottle"], (name, receipt)
        run("brew", "test", formula)
        run("brew", "linkage", "--test", "--strict", formula)
        print(f"PASS named-formula pour, receipt, test and linkage: {name}", flush=True)
    prefix = Path(subprocess.check_output(["brew", "--prefix"], text=True).strip())
    repository = Path(subprocess.check_output(["brew", "--repository"], text=True).strip())
    run(prefix / "opt/python@3.15/bin/python3.15", prefix / "opt/zathura/share/zathura/smoke-test.py",
        prefix / "opt/zathura/Zathura.app", repository / "Library/Homebrew/test/support/fixtures", prefix)
    run("python3", tap / "scripts/check-zathura-dependencies.py")
finally:
    for path, content in originals.items():
        path.write_bytes(content)
    for alias in aliases:
        alias.unlink()
    server.shutdown()
    server.server_close()
    metadata_directory.cleanup()

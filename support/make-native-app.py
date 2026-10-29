#!/usr/bin/env python3
"""Assemble a development-only native bundle from staged sources and tap assets."""
import os
from pathlib import Path
import plistlib
import shutil
import subprocess

root = Path(__file__).resolve().parent.parent
brew = os.environ.get("HOMEBREW_BREW_FILE") or shutil.which("brew") or "/opt/homebrew/bin/brew"

def query(*arguments):
    return Path(subprocess.check_output([brew, *arguments], text=True).strip())

prefix = query("--prefix")
assets = root / "packaging/homebrew-personal/assets/zathura"
if not assets.is_dir():
    raise SystemExit("Initialise packaging sources with git submodule update --init --recursive")
stage = root / "stage/dev"
app = root / "build/dev/Zathura Dev.app"
resources = app / "Contents/Resources"
macos = app / "Contents/MacOS"
resources.mkdir(parents=True, exist_ok=True)
macos.mkdir(parents=True, exist_ok=True)
shutil.copy2(stage / "bin/zathura", macos / "zathura")
for name in ("Zathura.icns", "session.conf"):
    shutil.copy2(assets / name, resources / name)
helper = (assets / "launcher.py").read_text()
for token, value in {
    "@@PYTHON@@": prefix / "opt/python@3.15/bin/python3.15",
    "@@HOMEBREW_PREFIX@@": prefix,
    "@@GDBUS@@": prefix / "opt/glib/bin/gdbus",
    "@@DBUS@@": prefix / "opt/dbus/bin/dbus-daemon",
    "@@PLUGINS@@": stage / "lib/zathura",
    "@@RUNTIME@@": "zathura-dev",
}.items():
    helper = helper.replace(token, str(value))
(resources / "launcher.py").write_text(helper)
(resources / "launcher.py").chmod(0o755)
info = plistlib.loads((assets / "Info.plist").read_bytes())
info.update(CFBundleIdentifier="org.pwmt.zathura.dev",
            CFBundleName="Zathura Dev", CFBundleDisplayName="Zathura Dev")
(app / "Contents/Info.plist").write_bytes(plistlib.dumps(info))
subprocess.run(["/usr/bin/plutil", "-lint", str(app / "Contents/Info.plist")], check=True)
subprocess.run(["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
print(app)

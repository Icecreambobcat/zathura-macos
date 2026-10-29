#!/usr/bin/env python3
"""Exercise a dedicated test bundle/private bus, never the live personal session."""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--app", required=True, type=Path)
parser.add_argument("--bus", required=True)
parser.add_argument("--fixtures", required=True, type=Path)
parser.add_argument("--report", required=True, type=Path)
args = parser.parse_args()
binary = args.app.resolve() / "Contents/MacOS/zathura"
brew_command = os.environ.get("HOMEBREW_BREW_FILE") or shutil.which("brew") or "/opt/homebrew/bin/brew"
brew = Path(subprocess.check_output([brew_command, "--prefix"], text=True).strip())
gdbus = str(brew / "bin/gdbus")
yabai = str(brew / "bin/yabai")
samples = []
checks = []

def run(command, **kwargs):
    return subprocess.run([str(x) for x in command], check=True, text=True,
                          capture_output=True, timeout=10, **kwargs).stdout.strip()

def bus(dest, method, *values, path="/org/pwmt/zathura"):
    return run([gdbus, "call", "--address", args.bus, "--timeout", "5",
                "--dest", dest, "--object-path", path, "--method", method, *values])

def endpoints():
    try:
        names = bus("org.freedesktop.DBus", "org.freedesktop.DBus.ListNames",
                    path="/org/freedesktop/DBus")
    except subprocess.CalledProcessError as error:
        if any(marker in error.stderr for marker in ("No such file", "Connection refused")):
            return {}
        raise RuntimeError(error.stderr) from error
    result = {}
    for name in re.findall(r"'([^']*PID-[^']*)'", names):
        try:
            value = bus(name, "org.freedesktop.DBus.Properties.Get", "org.pwmt.zathura", "filename")
        except subprocess.CalledProcessError as error:
            if any(marker in error.stderr for marker in ("No document", "ServiceUnknown", "NameHasNoOwner")):
                continue
            raise RuntimeError(error.stderr) from error
        result[name] = ast.literal_eval(value[value.index("<") + 1:value.rindex(">")])
    return result

def page(name):
    value = bus(name, "org.freedesktop.DBus.Properties.Get", "org.pwmt.zathura", "pagenumber")
    return int(re.search(r"uint32 (\d+)", value)[1])

def until(predicate, description):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError(description)

def passed(name):
    checks.append(name)
    print("PASS", name, flush=True)

def windows(pid):
    return [w for w in json.loads(run([yabai, "-m", "query", "--windows"])) if w["pid"] == pid]

def geometry(pid, label):
    # Allow normal asynchronous AX/GTK resize processing, then check it stays settled.
    for delay in (0.15, 0.4):
        time.sleep(delay)
        tiled = [w for w in windows(pid) if not w["is-floating"] and not w["is-minimized"]]
        samples.append({"stage": label, "windows": [{"id": w["id"], "frame": w["frame"]} for w in tiled]})
        for i, first in enumerate(tiled):
            a = first["frame"]
            assert a["w"] > 100 and a["h"] > 80, (label, a)
            for second in tiled[i + 1:]:
                if first["space"] != second["space"]:
                    continue
                b = second["frame"]
                overlap_x = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
                overlap_y = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
                assert overlap_x < 3 or overlap_y < 3, (label, a, b)

# Refuse to close or reuse an existing app's windows.
assert not endpoints(), "Use a dedicated, idle test bus, not the installed app's bus."
with tempfile.TemporaryDirectory(prefix="zathura-host-regression-") as temporary:
    root = Path(temporary)
    (root / "zathurarc").write_text("set database null\nset adjust-open width\nset guioptions s\n")
    options = ["-c", str(root), "-d", str(root), "--cache-dir", str(root)]
    one = (args.fixtures / "Project One/main.pdf").resolve()
    two = (args.fixtures / "Project Two/main.pdf").resolve()
    log_path = args.report.with_suffix(".log")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w") as log:
        host = subprocess.Popen([str(binary), *options, str(one), str(two)],
                                stdout=log, stderr=log)
        try:
            until(lambda: set(endpoints().values()) == {str(one), str(two)}, "two documents did not open")
            pid = int(re.search(r"PID-(\d+)", next(iter(endpoints())))[1])
            assert pid == host.pid, (pid, host.pid)
            until(lambda: len(windows(pid)) == 2, "two native windows did not appear")
            passed("one native host, two document endpoints/windows")
            run([binary, *options, one])
            assert len(endpoints()) == 2
            passed("duplicate open reuses its document window")
            run(["/usr/bin/open", "-a", args.app.resolve(), one, two])
            until(lambda: len(endpoints()) == 2 and len(windows(pid)) == 2,
                  "Launch Services open did not reuse the native host")
            assert host.poll() is None
            passed("Launch Services multi-file open reuses the native host")
            by_path = {v: k for k, v in endpoints().items()}
            first, second = by_path[str(one)], by_path[str(two)]
            bus(first, "org.pwmt.zathura.GotoPage", "0")
            bus(second, "org.pwmt.zathura.GotoPage", "1")
            until(lambda: page(first) == 0 and page(second) == 1, "page state is not independent")
            run([binary, *options, "-P", "2", one])
            until(lambda: page(first) == 1, "per-request page was ignored")
            run([binary, *options, "--synctex-forward", f"3:1:{one.with_suffix('.tex')}", one])
            until(lambda: page(first) == 0, "first-document forward search failed")
            assert page(second) == 1
            run([binary, *options, "--synctex-forward", f"3:1:{two.with_suffix('.tex')}", two])
            until(lambda: page(second) == 0, "second-document forward search failed")
            passed("per-window pages and filename-routed forward SyncTeX")
            geometry(pid, "initial")
            for index in range(8):
                target = windows(pid)[index % 2]["id"]
                run([yabai, "-m", "window", target, "--toggle", "float"])
                geometry(pid, f"float-{index}")
                run([yabai, "-m", "window", target, "--toggle", "float"])
                geometry(pid, f"retile-{index}")
            passed("eight float/retile cycles without tiled-window overlap")
            for index in range(6):
                neighbour = root / f"neighbour-{index}.pdf"
                neighbour.write_bytes(one.read_bytes())
                run([binary, *options, neighbour])
                until(lambda: len(endpoints()) == 3 and len(windows(pid)) == 3, "neighbour did not open")
                geometry(pid, f"neighbour-open-{index}")
                endpoint = next(k for k, v in endpoints().items() if v == str(neighbour))
                bus(endpoint, "org.pwmt.zathura.ExecuteCommand", "quit")
                until(lambda: len(endpoints()) == 2 and len(windows(pid)) == 2, "neighbour did not close independently")
                geometry(pid, f"neighbour-close-{index}")
            passed("six neighbouring-window open/close cycles without resize jumps")
            subprocess.run([str(binary), *options, "-"], input=one.read_bytes(),
                           check=True, capture_output=True, timeout=10)
            until(lambda: len(endpoints()) == 3, "stdin window did not open")
            endpoint, temporary_pdf = next((k, v) for k, v in endpoints().items() if v not in {str(one), str(two)})
            assert Path(temporary_pdf).exists()
            bus(endpoint, "org.pwmt.zathura.ExecuteCommand", "quit")
            until(lambda: not Path(temporary_pdf).exists(), "stdin spool was not removed")
            passed("stdin forwarding and temporary-file cleanup")
            bus(first, "org.pwmt.zathura.ExecuteCommand", "quit")
            until(lambda: len(endpoints()) == 1, "first window did not close")
            assert host.poll() is None and endpoints()[second] == str(two)
            passed("closing one document leaves the other alive")
            bus(second, "org.pwmt.zathura.ExecuteCommand", "quit")
            assert host.wait(timeout=8) == 0
            passed("closing the last document exits cleanly")
        finally:
            if host.poll() is None:
                host.terminate()
                host.wait(timeout=8)
            args.report.write_text(json.dumps({"checks": checks, "geometry_samples": samples,
                                               "log": str(log_path)}, indent=2) + "\n")
    diagnostics = log_path.read_text()
    assert not re.search(r"CRITICAL|AddressSanitizer|runtime error:|assertion .* failed", diagnostics), diagnostics[-4000:]
print(f"Report: {args.report}")

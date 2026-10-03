#!/usr/bin/env python3
"""
ComicCraftAI - one-file automatic fix (v2).

    python fix.py              reuse healthy .venv, repair, test, start server
    python fix.py --rebuild    recreate .venv from scratch
    python fix.py --deep       also smoke-test every parameterless GET route
    python fix.py --no-start   do everything except launching Uvicorn

Full logs of every run: repair_logs/fix_<timestamp>.log
"""
import argparse
import ast
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IS_WIN = os.name == "nt"
VENV = ROOT / ".venv"
VPY = VENV / ("Scripts/python.exe" if IS_WIN else "bin/python")
REQ = ROOT / "requirements.txt"
BACKUPS = ROOT / "repair_backups"
LOG_DIR = ROOT / "repair_logs"
LOG = LOG_DIR / f"fix_{time.strftime('%Y%m%d_%H%M%S')}.log"
IGNORED = {".venv", "__pycache__", ".git", "node_modules", "repair_backups", "repair_logs"}

CORE = [
    "fastapi", "uvicorn[standard]", "starlette", "jinja2", "python-multipart",
    "pydantic", "pydantic-settings", "pillow", "fpdf2", "python-dotenv",
    "requests", "httpx",
]
CORE_NAMES = {
    "fastapi", "uvicorn", "starlette", "jinja2", "python-multipart", "pydantic",
    "pydantic-core", "pydantic-settings", "pillow", "fpdf2", "python-dotenv",
    "requests", "httpx",
}
BINARY_ONLY = "pillow,pydantic-core"

# import name -> pip name (used when the app test finds a missing module)
PIP_NAMES = {
    "google.genai": "google-genai", "google.generativeai": "google-generativeai",
    "google": "google-genai", "PIL": "pillow", "cv2": "opencv-python",
    "dotenv": "python-dotenv", "yaml": "pyyaml", "bs4": "beautifulsoup4",
    "sklearn": "scikit-learn", "multipart": "python-multipart",
    "jose": "python-jose", "jwt": "pyjwt", "docx": "python-docx",
    "fitz": "pymupdf", "dateutil": "python-dateutil", "huggingface_hub": "huggingface_hub",
}

if IS_WIN:
    os.system("")  # enable ANSI colors


# ================================================================ output / log
def log(text):
    if not text:
        return
    try:
        LOG_DIR.mkdir(exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(str(text).rstrip() + "\n")
    except Exception:
        pass


def _p(tag, color, text):
    print(f"\033[{color}m[{tag}]\033[0m {text}", flush=True)
    log(f"[{tag}] {text}")


def info(t): _p("INFO", 96, t)
def ok(t): _p("OK", 92, t)
def warn(t): _p("WARN", 93, t)
def fail(t): _p("ERROR", 91, t)


def section(t):
    print(f"\n{'=' * 70}\n{t}\n{'=' * 70}", flush=True)
    log(f"\n=== {t} ===")


def die(msg):
    fail(msg)
    print(f"\nFull log: {LOG}")
    sys.exit(1)


def run(cmd, timeout=900, stream=False):
    """Never raises. Always returns an object with returncode/stdout/stderr."""
    cmd = [str(c) for c in cmd]
    log("$ " + " ".join(cmd[:6]) + (" ..." if len(cmd) > 6 else ""))
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    try:
        if stream:
            return subprocess.run(cmd, cwd=str(ROOT), env=env)
        r = subprocess.run(cmd, cwd=str(ROOT), env=env, text=True, encoding="utf-8",
                           errors="replace", capture_output=True, timeout=timeout)
    except FileNotFoundError as exc:
        r = subprocess.CompletedProcess(cmd, 127, "", str(exc))
    except subprocess.TimeoutExpired:
        r = subprocess.CompletedProcess(cmd, 124, "", f"timed out after {timeout}s")
    except Exception as exc:
        r = subprocess.CompletedProcess(cmd, 1, "", repr(exc))
    log(r.stdout)
    log(r.stderr)
    return r


def good(r):
    return r.returncode == 0


def tail(r, n=12):
    lines = ((r.stderr or "").strip() or (r.stdout or "").strip()).splitlines()[-n:]
    for line in lines:
        print("   | " + line)


def guard(fn, *args, critical=True):
    """Run a step; unexpected crashes are logged and reported cleanly."""
    try:
        return fn(*args)
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception:
        log(traceback.format_exc())
        msg = f"Step '{fn.__name__}' crashed unexpectedly: {sys.exc_info()[1]!r}"
        if critical:
            die(msg)
        warn(msg + " (continuing)")


# ================================================================ environment
def check_python():
    section("1. CHECKING PYTHON")
    v = sys.version_info
    print(f"Python {v.major}.{v.minor}.{v.micro}")
    if v < (3, 10):
        die("Python 3.10+ is required (3.11+ recommended).")
    ok("Python version is fine.")
    if "onedrive" in str(ROOT).lower():
        warn("Project is inside OneDrive. Syncing locks/slows .venv. "
             "Best: move the project out of OneDrive, or exclude .venv from sync.")


def stop_processes():
    section("2. STOPPING OLD PROJECT PROCESSES")
    if not IS_WIN:
        info("Not Windows, skipping.")
        return
    path = str(ROOT).replace("'", "''")
    ps = (
        f"$p='{path}'; $me={os.getpid()};"
        "Get-CimInstance Win32_Process | Where-Object {"
        "$_.Name -match 'python|uvicorn' -and $_.ProcessId -ne $me -and "
        "$_.CommandLine -and $_.CommandLine.Contains($p)} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    r = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], timeout=60)
    if good(r):
        time.sleep(1)
        ok("Processes checked.")
    else:
        warn("Could not query processes (continuing).")


def _force_remove(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove_venv():
    info("Removing old .venv ...")
    for attempt in range(3):
        try:
            shutil.rmtree(VENV, onerror=_force_remove)
        except Exception as exc:
            warn(f"Attempt {attempt + 1} failed: {exc}")
        if not VENV.exists():
            ok("Old .venv removed.")
            return
        time.sleep(1.5)
    if IS_WIN:
        run(["cmd", "/c", "rmdir", "/S", "/Q", VENV], timeout=120)
        if not VENV.exists():
            ok("Old .venv removed.")
            return
    new = ROOT / f".venv_old_{time.strftime('%Y%m%d_%H%M%S')}"
    try:
        VENV.rename(new)
        ok(f"Locked .venv renamed to {new.name}")
    except Exception as exc:
        die(f"Cannot remove or rename .venv: {exc}\n"
            "Close VS Code terminals and any running server, then rerun.")


def venv_healthy():
    if not VPY.exists():
        return False
    r = run([VPY, "-c", "import sys;print(sys.version_info.major, sys.version_info.minor)"], timeout=60)
    return good(r) and r.stdout.split() == [str(sys.version_info.major), str(sys.version_info.minor)]


def setup_venv(rebuild):
    section("3. VIRTUAL ENVIRONMENT")
    if VENV.exists() and not rebuild and venv_healthy():
        ok("Existing .venv is healthy, reusing it (use --rebuild to recreate).")
        return
    if VENV.exists():
        remove_venv()
    info("Creating new .venv ...")
    r = run([sys.executable, "-m", "venv", VENV], timeout=300)
    if not good(r) or not VPY.exists():
        tail(r)
        die("Failed to create the virtual environment.")
    ok("New .venv created.")


def pip(*args, timeout=900):
    return run([VPY, "-m", "pip", "--disable-pip-version-check", *args], timeout=timeout)


def install_core():
    section("4. INSTALLING PACKAGES")
    info("Upgrading pip/setuptools/wheel ...")
    r = pip("install", "-q", "--upgrade", "pip", "setuptools", "wheel")
    if not good(r):
        tail(r)
        die("pip upgrade failed. Check your internet connection / proxy.")
    info("Installing core packages (one pass) ...")
    base = ["install", "-q", "--upgrade", "--prefer-binary"]
    r = pip(*base, f"--only-binary={BINARY_ONLY}", *CORE)
    if not good(r):
        warn("Bulk install failed, retrying package by package ...")
        tail(r, 5)
        for pkg in CORE:
            r = pip(*base, pkg)
            if not good(r):
                tail(r)
                die(f"Could not install {pkg}.")
    ok("Core packages installed.")


def install_requirements():
    if not REQ.exists():
        info("No requirements.txt found.")
        return
    keep = []
    for raw in REQ.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "http://", "https://", "git+")):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)", line)
        if m and m.group(1).lower().replace("_", "-") not in CORE_NAMES:
            keep.append(line)
    if not keep:
        ok("No extra project requirements.")
        return
    info(f"Installing {len(keep)} project requirement(s): {', '.join(keep)}")
    if good(pip("install", "-q", "--prefer-binary", *keep)):
        ok("Project requirements installed.")
        return
    warn("Bulk install failed, trying one by one ...")
    for pkg in keep:
        r = pip("install", "-q", "--prefer-binary", pkg)
        if good(r):
            ok(pkg)
        else:
            warn(f"Failed: {pkg}")
            tail(r, 4)


def pip_check():
    r = pip("check", timeout=120)
    if good(r):
        ok("No dependency conflicts.")
    else:
        warn("pip reports dependency conflicts (usually harmless if the app runs):")
        for line in (r.stdout or "").strip().splitlines()[:6]:
            print("   | " + line)


# ================================================================ code repair
def _offsets(src):
    offs = [0]
    for i, b in enumerate(src):
        if b == 10:
            offs.append(i + 1)
    return offs


def _span(offs, node):
    return (offs[node.lineno - 1] + node.col_offset,
            offs[node.end_lineno - 1] + node.end_col_offset)


def _has_request(d):
    return any(isinstance(k, ast.Constant) and k.value == "request" for k in d.keys)


def _rewrite_call(node, src, offs):
    """Return new call text, 'manual', or None (already fine / not applicable)."""
    def S(n):
        a, b = _span(offs, n)
        return src[a:b].decode("utf-8")

    def split_ctx(d):
        req, items = None, []
        for k, v in zip(d.keys, d.values):
            if isinstance(k, ast.Constant) and k.value == "request":
                req = v
            elif k is None:
                items.append("**" + S(v))
            else:
                items.append(f"{S(k)}: {S(v)}")
        return req, items

    args, kws = list(node.args), list(node.keywords)
    kwmap = {k.arg: k for k in kws if k.arg}
    parts = None

    if args and isinstance(args[0], ast.Dict) and _has_request(args[0]):
        # TemplateResponse({"request": request, ...}, "name.html", ...)
        if len(args) < 2:
            return "manual"
        req, items = split_ctx(args[0])
        name, rest = args[1], args[2:]
        ctx = "{" + ", ".join(items) + "}" if items else ("{}" if rest else None)
        parts = [S(req), S(name)] + ([ctx] if ctx else []) + [S(a) for a in rest] + [S(k) for k in kws]

    elif args and isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
        # TemplateResponse("name.html", {"request": request, ...}, ...)
        name = args[0]
        ctx_node, rest, other_kws = None, [], kws
        if len(args) >= 2 and isinstance(args[1], ast.Dict) and _has_request(args[1]):
            ctx_node, rest = args[1], args[2:]
        elif "context" in kwmap and isinstance(kwmap["context"].value, ast.Dict) \
                and _has_request(kwmap["context"].value):
            ctx_node, rest = kwmap["context"].value, args[1:]
            other_kws = [k for k in kws if k.arg != "context"]
        else:
            return "manual"
        req, items = split_ctx(ctx_node)
        ctx = "{" + ", ".join(items) + "}" if items else ("{}" if rest else None)
        parts = [S(req), S(name)] + ([ctx] if ctx else []) + [S(a) for a in rest] + [S(k) for k in other_kws]

    elif not args and "name" in kwmap and "context" in kwmap and "request" not in kwmap \
            and isinstance(kwmap["context"].value, ast.Dict) and _has_request(kwmap["context"].value):
        # TemplateResponse(name="x.html", context={"request": request})
        req, items = split_ctx(kwmap["context"].value)
        parts = [S(req), f"name={S(kwmap['name'].value)}"]
        if items:
            parts.append("context={" + ", ".join(items) + "}")
        parts += [S(k) for k in kws if k.arg not in ("name", "context")]

    if parts is None:
        return None

    func = S(node.func)
    one = f"{func}({', '.join(parts)})"
    if len(one) <= 88:
        return one
    a, _ = _span(offs, node)
    line_start = max(i for i in offs if i <= a)
    prefix = src[line_start:a].decode("utf-8", "ignore")
    indent = re.match(r"\s*", prefix).group(0)
    inner = (",\n" + indent + "    ").join(parts)
    return f"{func}(\n{indent}    {inner},\n{indent})"


def repair_template_response(text):
    """AST-based: returns (new_text, changed_count, manual_line_numbers)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text, 0, []
    src = text.encode("utf-8")
    offs = _offsets(src)
    edits, manual = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "TemplateResponse":
            new = _rewrite_call(node, src, offs)
            if new == "manual":
                manual.append(node.lineno)
            elif new:
                a, b = _span(offs, node)
                edits.append((a, b, new))
    out, limit, count = src, len(src) + 1, 0
    for a, b, new in sorted(edits, key=lambda e: e[0], reverse=True):
        if b > limit:  # nested inside an already-rewritten call
            continue
        out = out[:a] + new.encode("utf-8") + out[b:]
        limit, count = a, count + 1
    result = out.decode("utf-8")
    try:
        ast.parse(result)
    except SyntaxError:
        return text, 0, manual
    return result, count, manual


def py_files():
    me = Path(__file__).resolve()
    for f in ROOT.rglob("*.py"):
        if f != me and not IGNORED.intersection(f.relative_to(ROOT).parts):
            yield f


def backup(f):
    dest = BACKUPS / f.relative_to(ROOT)
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)


def repair_code():
    section("5. REPAIRING PROJECT CODE")
    changed = 0
    for f in py_files():
        try:
            text = f.read_text(encoding="utf-8")
        except Exception as exc:
            warn(f"Cannot read {f.relative_to(ROOT)}: {exc}")
            continue
        if "TemplateResponse" not in text:
            continue
        new, n, manual = repair_template_response(text)
        rel = f.relative_to(ROOT)
        if n:
            try:
                backup(f)
                f.write_text(new, encoding="utf-8")
                changed += 1
                ok(f"Repaired {n} TemplateResponse call(s) in {rel}")
            except Exception as exc:
                warn(f"Could not write {rel}: {exc}")
        for line in manual:
            warn(f"{rel}:{line} TemplateResponse uses the old signature but could not be "
                 "auto-fixed. Use: templates.TemplateResponse(request, 'page.html', {...})")
    info(f"{changed} file(s) changed." + (f" Backups: {BACKUPS.name}/" if changed else ""))


def check_syntax():
    section("6. CHECKING PYTHON SYNTAX")
    bad = 0
    for f in py_files():
        try:
            ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except SyntaxError as exc:
            bad += 1
            fail(f"{f.relative_to(ROOT)}:{exc.lineno}: {exc.msg}")
        except Exception:
            pass
    if bad:
        die(f"{bad} file(s) have syntax errors. Fix them and rerun.")
    ok("No syntax errors.")


# ================================================================ verification
IMPORT_CHECK = r'''
mods = [("fastapi","FastAPI"),("uvicorn","Uvicorn"),("starlette","Starlette"),
        ("jinja2","Jinja2"),("pydantic","Pydantic"),("pydantic_core","Pydantic Core"),
        ("PIL","Pillow"),("requests","Requests"),("httpx","HTTPX")]
bad = False
for m, n in mods:
    try:
        mod = __import__(m); print("[OK]", n, getattr(mod, "__version__", ""))
    except Exception as e:
        print("[FAILED]", n, e); bad = True
raise SystemExit(1 if bad else 0)
'''

APP_CHECK = r'''
import importlib, json, os, sys, traceback, warnings
warnings.simplefilter("ignore")
root = os.path.abspath(sys.argv[1]); deep = sys.argv[2] == "1"
os.chdir(root); sys.path.insert(0, root)

def finish(**kw):
    print("RESULT " + json.dumps(kw)); raise SystemExit(0 if kw.get("ok") else 1)

def describe(exc):
    while getattr(exc, "exceptions", None):
        exc = exc.exceptions[0]
    tb = traceback.extract_tb(exc.__traceback__)
    frames = ["%s:%s in %s -> %s" % (os.path.relpath(f.filename, root), f.lineno, f.name, f.line)
              for f in tb if f.filename.startswith(root) and ".venv" not in f.filename]
    missing = exc.name if isinstance(exc, ModuleNotFoundError) else None
    return dict(type=type(exc).__name__, msg=str(exc)[:700], frames=frames[-6:], missing=missing,
                full="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))

app = target = None
for mod in ("app.main", "main", "app.app", "app"):
    try:
        m = importlib.import_module(mod)
    except ModuleNotFoundError as e:
        if e.name == mod or (e.name and mod.startswith(e.name + ".") ):
            continue
        finish(ok=False, stage="import " + mod, **describe(e))
    except BaseException as e:
        finish(ok=False, stage="import " + mod, **describe(e))
    if hasattr(m, "app"):
        app, target = m.app, mod + ":app"
        break
if app is None:
    finish(ok=False, stage="find app", type="NoApp", frames=[], missing=None, full="",
           msg="No FastAPI instance named 'app' found in app.main, main, app.app or app.")

from fastapi.testclient import TestClient
client = TestClient(app)
paths = ["/", "/openapi.json"]
if deep:
    for r in getattr(app, "routes", []):
        p = getattr(r, "path", "")
        if "GET" in (getattr(r, "methods", None) or ()) and "{" not in p and p not in paths:
            paths.append(p)
statuses, problems = {}, []
for p in paths:
    try:
        resp = client.get(p)
        statuses[p] = resp.status_code
        if resp.status_code >= 500:
            problems.append(dict(path=p, type="HTTP%d" % resp.status_code, msg=resp.text[:300],
                                 frames=[], missing=None, full=""))
    except BaseException as e:
        statuses[p] = "EXC"
        problems.append(dict(path=p, **describe(e)))
root_problem = next((p for p in problems if p["path"] == "/"), None)
if root_problem:
    finish(ok=False, stage="GET /", **{k: v for k, v in root_problem.items() if k != "path"})
finish(ok=True, target=target, statuses=statuses, problems=problems)
'''

HINTS = [
    (r"unhashable type: 'dict'",
     "A TemplateResponse still uses the old signature (Starlette 1.x removed it). "
     "Use: templates.TemplateResponse(request, 'page.html', {...})."),
    (r"TemplateNotFound",
     "Jinja cannot find that template. Check Jinja2Templates(directory=...) and that the file exists."),
    (r"UndefinedError",
     "A template uses a variable the route did not pass in its context."),
    (r"api[_ ]?key|GEMINI|GOOGLE_API|credentials|HF_TOKEN",
     "A secret is missing. Create a .env file next to fix.py (e.g. GEMINI_API_KEY=...) "
     "and make sure the code calls load_dotenv()."),
    (r"ValidationError",
     "Settings validation failed: a required environment variable is missing from .env."),
    (r"cannot import name",
     "Installed package version does not match what the code expects. Check requirements.txt."),
    (r"has no attribute",
     "An API used by the code was removed or renamed in the installed package version."),
    (r"FileNotFoundError|No such file",
     "A file or folder the app expects is missing (relative paths resolve from the project folder)."),
    (r"PermissionError",
     "A file is locked. Close other programs; if the project is in OneDrive, pause sync."),
]


def show_failure(d, stage):
    fail(f"App test failed at {stage}: {d.get('type')}: {d.get('msg')}")
    for fr in d.get("frames", []):
        print("   at " + fr)
    text = f"{d.get('type')} {d.get('msg')}"
    for pattern, hint in HINTS:
        if re.search(pattern, text, re.I):
            print(f"   HINT: {hint}")
            break
    log(d.get("full", ""))


def parse_result(r):
    for line in reversed((r.stdout or "").splitlines()):
        if line.startswith("RESULT "):
            try:
                return json.loads(line[7:])
            except ValueError:
                return None
    return None


def auto_heal(d, tried):
    """Try to fix the failure automatically. True if something changed."""
    missing = d.get("missing")
    if missing:
        top = missing.split(".")[0]
        local = (ROOT / top).exists() or (ROOT / f"{top}.py").exists()
        if local or top in sys.stdlib_module_names:
            return False
        pkg = PIP_NAMES.get(missing) or PIP_NAMES.get(top) or top.replace("_", "-")
        if pkg in tried:
            return False
        tried.add(pkg)
        info(f"Missing module '{missing}', installing '{pkg}' ...")
        r = pip("install", "-q", "--prefer-binary", pkg)
        if good(r):
            ok(f"Installed {pkg}.")
            return True
        tail(r, 4)
        return False
    m = re.search(r"Directory '(.+?)' does not exist", d.get("msg", ""))
    if m:
        target = (ROOT / m.group(1)).resolve()
        if ROOT in target.parents or target == ROOT:
            target.mkdir(parents=True, exist_ok=True)
            ok(f"Created missing folder: {m.group(1)}")
            return True
    return False


def verify_and_test(deep):
    section("7. VERIFYING PACKAGES")
    r = run([VPY, "-c", IMPORT_CHECK], timeout=120)
    print(r.stdout.strip())
    if not good(r):
        die("Package verification failed.")
    ok("All critical packages import correctly.")

    section("8. TESTING FASTAPI APP")
    tried = set()
    for _ in range(5):
        r = run([VPY, "-W", "ignore", "-c", APP_CHECK, ROOT, "1" if deep else "0"], timeout=180)
        data = parse_result(r)
        if data is None:
            fail("The app test crashed before reporting a result:")
            tail(r, 15)
            die("App test could not run.")
        if data.get("ok"):
            for path, status in data["statuses"].items():
                print(f"   GET {path} -> {status}")
            for p in data.get("problems", []):
                warn(f"GET {p['path']} failed: {p['type']}: {p['msg'][:150]}")
            ok(f"App '{data['target']}' responds correctly.")
            return data["target"]
        show_failure(data, data.get("stage", "?"))
        if not auto_heal(data, tried):
            break
        info("Retrying app test ...")
    die("The app still fails. Fix the error shown above, then rerun python fix.py.")


# ================================================================ start
def free_port(host, port):
    for p in range(port, port + 20):
        with socket.socket() as s:
            if s.connect_ex((host, p)) != 0:
                return p
    return port


def start_server(target, host, port):
    chosen = free_port(host, int(port))
    if chosen != int(port):
        warn(f"Port {port} is busy, using {chosen}.")
    section(f"9. STARTING SERVER  http://{host}:{chosen}   (Ctrl+C to stop)")
    try:
        run([VPY, "-m", "uvicorn", target, "--host", host, "--port", chosen, "--reload"], stream=True)
    except KeyboardInterrupt:
        pass
    print()
    info("Server stopped.")


# ================================================================ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--deep", action="store_true")
    ap.add_argument("--no-start", action="store_true")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", default="8000")
    args = ap.parse_args()

    t0 = time.time()
    guard(check_python)
    guard(stop_processes, critical=False)
    guard(setup_venv, args.rebuild)
    guard(install_core)
    guard(install_requirements, critical=False)
    guard(pip_check, critical=False)
    guard(repair_code, critical=False)
    guard(check_syntax)
    target = guard(verify_and_test, args.deep)
    ok(f"All checks passed in {time.time() - t0:.0f}s.")
    if not args.no_start:
        guard(start_server, target, args.host, args.port)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        warn("Cancelled.")
        sys.exit(130)
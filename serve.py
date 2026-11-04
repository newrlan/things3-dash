#!/usr/bin/env python3
"""Serves this folder on localhost and rebuilds the page on every load.

A page opened as a file:// document cannot run anything on the machine.
Served over http from here, every GET of things3-dash.html first runs
refresh.sh, so reloading the page in the browser shows fresh data. When the
build fails, the previous page is served with the error in its header.

    python3 serve.py            # then open http://127.0.0.1:8765/things3-dash.html

Binds to the loopback interface only: nothing outside this machine can reach it.
The only command it will ever run is refresh.sh sitting next to this file.
"""

import html
import http.server
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "refresh.sh")
PAGE = "things3-dash.html"
SLOT = '<span class="rstat" id="rstat"></span>'   # the template's status slot
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765


def refresh():
    """Runs refresh.sh; returns (ok, its output)."""
    print("-- запуск refresh.sh", flush=True)
    try:
        # stdin of a detached server may be closed; a child python inheriting
        # it dies in init_sys_streams before running a line
        r = subprocess.run([SCRIPT], stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, timeout=300)
        ok, out = r.returncode == 0, (r.stdout + r.stderr).strip()[-4000:]
    except Exception as e:                          # noqa: BLE001 - report anything back to the page
        ok, out = False, str(e)
    print(out, flush=True)
    return ok, out


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def do_GET(self):
        if self.path.split("?", 1)[0] != "/" + PAGE:
            super().do_GET()
            return
        ok, out = refresh()
        if ok:
            super().do_GET()
            return
        last = next((l for l in reversed(out.splitlines()) if l.strip()), "не удалось")
        msg = html.escape("обновить данные не удалось: " + last)
        try:
            with open(os.path.join(HERE, PAGE), encoding="utf-8") as f:
                page = f.read()
        except OSError:
            page = ""
        if SLOT in page:
            page = page.replace(SLOT, f'<span class="rstat err" id="rstat">{msg}</span>', 1)
        else:                                       # no previous page to fall back to
            page = (f"<!doctype html><meta charset=utf-8><title>things3-dash</title>"
                    f"<pre>{html.escape(out)}</pre>")
        data = page.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def end_headers(self):
        # pages are rebuilt in place; never let the browser serve a stale copy
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


if not os.access(SCRIPT, os.X_OK):
    sys.exit(f"refresh.sh не найден или не исполняемый: {SCRIPT}")

with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as httpd:
    print(f"открывайте http://127.0.0.1:{PORT}/{PAGE}", flush=True)
    print("остановить: Ctrl+C", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")

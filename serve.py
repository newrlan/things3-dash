#!/usr/bin/env python3
"""Serves this folder on localhost and lets the page trigger refresh.sh.

A page opened as a file:// document cannot run anything on the machine.
Served over http from here, the "Обновить данные" button can POST /refresh,
and this process runs refresh.sh on its behalf.

    python3 serve.py            # then open http://127.0.0.1:8765/week.html

Binds to the loopback interface only: nothing outside this machine can reach it.
The only command it will ever run is refresh.sh sitting next to this file.
"""

import http.server
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "refresh.sh")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def do_POST(self):
        if self.path != "/refresh":
            self.send_error(404)
            return
        print("-- запуск refresh.sh", flush=True)
        try:
            r = subprocess.run([SCRIPT], capture_output=True, text=True, timeout=300)
            body = {"ok": r.returncode == 0,
                    "out": (r.stdout + r.stderr).strip()[-4000:]}
        except Exception as e:                      # noqa: BLE001 - report anything back to the page
            body = {"ok": False, "out": str(e)}
        print(body["out"], flush=True)
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
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
    print(f"открывайте http://127.0.0.1:{PORT}/week.html", flush=True)
    print("остановить: Ctrl+C", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")

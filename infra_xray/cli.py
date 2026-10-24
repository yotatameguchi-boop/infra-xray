"""Read-only CLI and localhost-only HTTP server."""
import argparse
import json
import secrets
import sys
import webbrowser
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from .parser import load_plan, PlanError

STATIC = Path(__file__).parent / "static"

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # URLs, file paths, or plan values must not enter request logs.

    def respond(self, status, body, content_type="text/plain; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        port = self.server.server_address[1]
        if self.headers.get("Host") != "127.0.0.1:" + str(port):
            return self.respond(403, b"Forbidden")
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            return self.respond(403, b"Forbidden")
        parsed = urlparse(self.path)
        if parsed.path == "/api/graph":
            auth = self.headers.get("Authorization", "")
            if not secrets.compare_digest(auth, "Bearer " + self.server.token):
                return self.respond(403, b"Forbidden")
            return self.respond(200, self.server.graph_bytes, "application/json; charset=utf-8")
        relative = parsed.path.lstrip("/") or "index.html"
        path = (STATIC / relative).resolve()
        if STATIC.resolve() not in path.parents or not path.is_file():
            return self.respond(404, b"Not found")
        types = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}
        return self.respond(200, path.read_bytes(), types.get(path.suffix, "application/octet-stream"))

def make_server(graph, port=0):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.token = secrets.token_urlsafe(32)
    server.graph_bytes = json.dumps(graph, ensure_ascii=False, allow_nan=False).encode()
    return server

def main(argv=None):
    parser = argparse.ArgumentParser(prog="infra-xray", description="Terraform planをローカルで解析・可視化します。")
    sub = parser.add_subparsers(dest="command", required=True)
    view = sub.add_parser("view", help="ローカルUIを起動")
    view.add_argument("plan")
    view.add_argument("--port", type=int, default=0, help="0: 空きポートを自動選択")
    view.add_argument("--no-open", action="store_true")
    check = sub.add_parser("check", help="許可リストで抽出した解析結果をJSON出力")
    check.add_argument("plan")
    args = parser.parse_args(argv)
    try:
        graph = load_plan(args.plan)
        if args.command == "check":
            print(json.dumps(graph, ensure_ascii=False, indent=2, allow_nan=False))
            return 0
        if not (STATIC / "index.html").is_file():
            raise PlanError("UIが未ビルドです。webで npm ci && npm run build を実行してください。")
        if not 0 <= args.port <= 65535:
            raise PlanError("portは0〜65535を指定してください。")
        server = make_server(graph, args.port)
    except PlanError as error:
        print("エラー: " + str(error), file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, RecursionError):
        # Do not stringify library exceptions: they can contain input values.
        print("エラー: plan形式・ファイル・ポート・UIビルドを確認してください。", file=sys.stderr)
        return 2
    url = "http://127.0.0.1:" + str(server.server_address[1]) + "/#token=" + server.token
    print("Infra X-Ray: " + url, flush=True)
    print("ローカル解析のみ。終了: Ctrl+C", flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0

if __name__ == "__main__":
    sys.exit(main())

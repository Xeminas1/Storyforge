"""Launch with: py server.py (Windows) or python server.py."""
from __future__ import annotations

import json
import os
import logging
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import engine
import narration
import updater

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DB_PATH = Path(os.getenv("STORYFORGE_DB", str(ROOT / "data" / "storyforge.db")))
HOST = os.getenv("STORYFORGE_HOST", "127.0.0.1")
PORT = int(os.getenv("STORYFORGE_PORT", "8787"))


class Handler(BaseHTTPRequestHandler):
    server_version = "Storyforge/0.4.0"

    def _send(self, status: int, data: bytes, mime: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; media-src 'self' blob:; object-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def reply(self, result: object, status: int = 200) -> None:
        self._send(status, json.dumps(result, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def read_body(self, max_bytes: int = 300_000) -> bytes:
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Invalid request length")
        if n < 1 or n > max_bytes:
            raise ValueError("Request is empty or too large")
        return self.rfile.read(n)

    def json_body(self) -> dict:
        result = json.loads(self.read_body().decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError("Expected a JSON object")
        return result

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path.startswith("/api/"):
                with engine.open_db(DB_PATH) as con:
                    if path == "/api/health":
                        return self.reply({"ok": True, "version": updater.VERSION, "model": "local Ollama"})
                    if path == "/api/updates":
                        return self.reply(updater.get_status(ROOT))
                    if path == "/api/tts/status":
                        return self.reply(narration.status())
                    if path == "/api/models":
                        return self.reply({"models": engine.list_local_models()})
                    if path == "/api/worlds":
                        return self.reply({"worlds": engine.list_worlds(con)})
                    if path.startswith("/api/worlds/"):
                        return self.reply({"world": engine.get_world(con, path.rsplit("/", 1)[1])})
                    if path == "/api/campaigns":
                        return self.reply({"campaigns": engine.list_campaigns(con)})
                    if path.startswith("/api/campaigns/"):
                        parts = path.split("/")
                        campaign_id = parts[3]
                        if len(parts) == 5 and parts[4] == "messages":
                            return self.reply({"messages": engine.get_messages(con, campaign_id)})
                        if len(parts) == 4:
                            return self.reply({"campaign": engine.get_campaign(con, campaign_id)})
            elif path in ("/", "/index.html", "/styles.css", "/app.js"):
                filename = "index.html" if path == "/" else path.lstrip("/")
                mime = {".html": "text/html", ".css": "text/css", ".js": "application/javascript"}[Path(filename).suffix]
                return self._send(200, (STATIC / filename).read_bytes(), mime + "; charset=utf-8")
            return self.reply({"error": "Not found"}, 404)
        except LookupError as exc:
            return self.reply({"error": str(exc)}, 404)
        except (ValueError, json.JSONDecodeError) as exc:
            return self.reply({"error": str(exc)}, 400)
        except Exception:
            logging.exception("GET failed")
            return self.reply({"error": "Unexpected server error"}, 500)

    def do_PATCH(self) -> None:
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc != self.headers.get("Host"):
            return self.reply({"error": "Cross-origin requests are not allowed"}, 403)
        parts = urlparse(self.path).path.split("/")
        if len(parts) != 5 or parts[:3] != ["", "api", "campaigns"] or parts[4] != "character":
            return self.reply({"error": "Not found"}, 404)
        try:
            with engine.open_db(DB_PATH) as con:
                return self.reply({"campaign": engine.update_character(con, parts[3], self.json_body())})
        except LookupError as exc:
            return self.reply({"error": str(exc)}, 404)
        except (ValueError, json.JSONDecodeError) as exc:
            return self.reply({"error": str(exc)}, 400)
        except Exception:
            logging.exception("PATCH failed")
            return self.reply({"error": "Unexpected server error"}, 500)

    def do_POST(self) -> None:
        # Block cross-site writes. Deliberately no permissive CORS headers.
        origin = self.headers.get("Origin")
        if origin:
            incoming = urlparse(origin)
            if incoming.netloc != self.headers.get("Host"):
                return self.reply({"error": "Cross-origin requests are not allowed"}, 403)
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/updates/activity":
                # No privileged operation; keep a playing/reading session active
                # so an unattended update doesn't interrupt a visible game.
                self.server.release_watcher.user_active()
                return self.reply({"ok": True})
            if path.startswith("/api/updates/"):
                # Installing executable code is possible only from the same PC,
                # not from a remotely connected browser or other websites.
                if self.client_address[0] not in ("127.0.0.1", "::1"):
                    return self.reply({"error": "Install updates from a browser on the host PC."}, 403)
                origin = self.headers.get("Origin", "")
                host_header = urlparse("http://" + self.headers.get("Host", ""))
                parsed_origin = urlparse(origin)
                if (not origin or parsed_origin.scheme != "http" or
                    host_header.hostname not in ("127.0.0.1", "localhost", "::1") or
                    parsed_origin.netloc != self.headers.get("Host")):
                    return self.reply({"error": "Update requests require the local Storyforge interface."}, 403)
                if path == "/api/updates/auto":
                    body = self.json_body()
                    val = updater.set_channel_enabled(ROOT, body.get('enabled'))
                    if val:
                        self.server.release_watcher.check_now()
                    return self.reply({'ok': True, 'enabled': val})
                if path == "/api/updates/check":
                    self.server.release_watcher.check_now()
                    return self.reply({'ok': True, 'message': 'Release check queued'})
                if path == "/api/updates/inspect":
                    payload = self.read_body(updater.MAX_ZIP_SIZE)
                    return self.reply(updater.stage_package(ROOT, payload))
                if path == "/api/updates/install":
                    payload = self.json_body()
                    if payload.get("confirm") != "INSTALL":
                        return self.reply({"error": "Installation confirmation is required."}, 400)
                    result = updater.begin_install(ROOT, DB_PATH, str(payload.get("token", "")),
                                                   self.server, self.server.server_address[0], self.server.server_address[1])
                    return self.reply(result)
                return self.reply({"error": "Not found"}, 404)
            self.server.release_watcher.user_active()
            with engine.open_db(DB_PATH) as con:
                if path == "/api/worlds":
                    return self.reply({"world": engine.make_world(con, self.json_body())}, 201)
                if path == "/api/worlds/import-zip":
                    args = parse_qs(parsed.query)
                    raw = self.read_body(engine.MAX_ZIP_BYTES)
                    world = engine.import_world_zip(con, raw,
                        title=args.get("title", [""])[0],
                        author=args.get("author", [""])[0],
                        source=args.get("source", [""])[0])
                    return self.reply({"world": world}, 201)
                if path == "/api/tts/speech":
                    audio = narration.synthesize(self.json_body())
                    return self._send(200, audio, "audio/mpeg")
                if path == "/api/campaigns":
                    return self.reply({"campaign": engine.new_campaign(con, self.json_body())}, 201)
                if path.startswith("/api/campaigns/") and path.endswith("/turn"):
                    parts = path.split("/")
                    if len(parts) != 5:
                        return self.reply({"error": "Not found"}, 404)
                    payload = self.json_body()
                    return self.reply(engine.play_turn(con, parts[3], str(payload.get("action", "")), model=str(payload.get("model", "qwen3:8b"))))
            return self.reply({"error": "Not found"}, 404)
        except LookupError as exc:
            return self.reply({"error": str(exc)}, 404)
        except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
            return self.reply({"error": str(exc)}, 400)
        except RuntimeError as exc:
            return self.reply({"error": str(exc)}, 503)
        except Exception:
            logging.exception("POST failed")
            return self.reply({"error": "Unexpected server error"}, 500)


def bootstrap() -> None:
    with engine.open_db(DB_PATH) as con:
        if not engine.list_worlds(con):
            engine.make_world(con, engine.DEMO_WORLD)


def run(host: str = HOST, port: int = PORT):
    bootstrap()
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("WARNING: This version has no login. Use only on a trusted private network such as Tailscale.")
    server = ThreadingHTTPServer((host, port), Handler)
    server.release_watcher = updater.UpdateWatcher(ROOT, DB_PATH, server)
    server.release_watcher.start()
    print(f"Storyforge v{updater.VERSION} running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Storyforge")
    finally:
        server.release_watcher.stop.set()
        server.server_close()


if __name__ == "__main__":
    run()

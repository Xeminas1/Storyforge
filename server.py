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
import lore
import engine as artwork
import narration
import updater

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DB_PATH = Path(os.getenv("STORYFORGE_DB", str(ROOT / "data" / "storyforge.db")))
HOST = os.getenv("STORYFORGE_HOST", "127.0.0.1")
PORT = int(os.getenv("STORYFORGE_PORT", "8787"))


class Handler(BaseHTTPRequestHandler):
    server_version = "Storyforge/0.10.0"

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
                    if path == "/api/artwork/status":
                        return self.reply(artwork.comfy_status())
                    if path == '/api/artwork/job':
                        args = parse_qs(parsed.query)
                        campaign = engine.get_campaign(con,args.get('campaign_id',[''])[0])
                        return self.reply({'job':artwork.job_status(args.get('kind',['portrait'])[0],campaign)})
                    if path == "/api/artwork/scene":
                        cid = parse_qs(parsed.query).get('campaign_id', [''])[0]
                        campaign = engine.get_campaign(con, cid)
                        scene = artwork.scene_record(con, campaign['world_id'],
                            campaign['state'].get('location','Unknown'), DB_PATH)
                        return self.reply({'scene':scene})
                    if path.startswith('/api/artwork/portraits/'):
                        cid = path.removeprefix('/api/artwork/portraits/')
                        campaign = engine.get_campaign(con, cid)
                        file = artwork.character_file(DB_PATH, campaign['id'])
                        if file is None: return self.reply({'error':'No character image'},404)
                        return self._send(200, file.read_bytes(),
                              {'png':'image/png','jpg':'image/jpeg','webp':'image/webp'}[file.suffix[1:]])
                    if path.startswith('/api/artwork/scenes/'):
                        parts = path.split('/')
                        if len(parts) != 6: return self.reply({'error':'Not found'},404)
                        world_id,key = parts[4],parts[5]
                        if not __import__('re').fullmatch(r'[a-f0-9]{32}', key):
                            return self.reply({'error':'Bad scene id'},400)
                        engine.get_world(con,world_id)
                        file=artwork.scene_file(con,world_id,key,DB_PATH)
                        if not file: return self.reply({'error':'Scene image not found'},404)
                        return self._send(200,file.read_bytes(),'image/png')
                    if path == "/api/tts/status":
                        return self.reply(narration.status())
                    if path == "/api/models":
                        return self.reply({"models": engine.list_local_models()})
                    if path == "/api/worlds":
                        return self.reply({"worlds": engine.list_worlds(con)})
                    if path.startswith("/api/worlds/"):
                        return self.reply({"world": engine.get_world(con, path.rsplit("/", 1)[1])})
                    if path == "/api/characters":
                        return self.reply({"characters": engine.list_characters(con)})
                    if path.startswith("/api/characters/"):
                        bits=path.split('/')
                        if len(bits)==5 and bits[4]=='portrait':
                            ident=bits[3]
                            engine.get_character(con, ident)
                            file=artwork.character_file(DB_PATH, ident)
                            if not file: return self.reply({'error':'Portrait not found'},404)
                            return self._send(200,file.read_bytes(),
                              {'png':'image/png','jpg':'image/jpeg','webp':'image/webp'}[file.suffix[1:]])
                        if len(bits)==4:
                            return self.reply({'character':engine.get_character(con,bits[3])})
                    if path.startswith('/api/spell-images/'):
                        ident=path.split('/')[-1]
                        if not __import__('re').fullmatch(r'[a-f0-9-]{36}',ident):
                            return self.reply({'error':'Invalid spell id'},400)
                        file=artwork.spell_image_file(DB_PATH,ident)
                        if not file: return self.reply({'error':'Image not found'},404)
                        return self._send(200,file.read_bytes(),
                            {'png':'image/png','jpg':'image/jpeg','webp':'image/webp'}[file.suffix[1:]])
                    if path.startswith('/api/characters/') and '/spells/' in path and path.endswith('/job'):
                        parts=path.split('/')
                        if len(parts)!=7:return self.reply({'error':'Not found'},404)
                        ch=engine.get_character(con,parts[3]);spell=artwork.find_spell(ch['profile'],parts[5])
                        return self.reply({'job':artwork.spell_job_status(spell['id'])})
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
        if len(parts)==5 and parts[:2]==['','api'] and parts[4]=='abilities' and parts[2] in ('campaigns','characters'):
            try:
                body=self.json_body()
                with engine.open_db(DB_PATH) as con:
                    if parts[2]=='campaigns':
                        return self.reply({'campaign':engine.save_campaign_abilities(con,parts[3],body.get('abilities'))})
                    return self.reply({'character':engine.save_library_abilities(con,parts[3],body.get('abilities'))})
            except LookupError as exc:return self.reply({'error':str(exc)},404)
            except (ValueError,TypeError) as exc:return self.reply({'error':str(exc)},400)
        if len(parts) != 5 or parts[:2] != ["", "api"] or not (
           (parts[2] == 'campaigns' and parts[4] == 'character') or
           (parts[2] == 'characters' and parts[4] == 'profile')):
            return self.reply({"error": "Not found"}, 404)
        try:
            with engine.open_db(DB_PATH) as con:
                if parts[2]=='characters':
                    return self.reply({'character':engine.edit_library_character(con,parts[3],self.json_body())})
                result=engine.update_character(con, parts[3], self.json_body())
                return self.reply({"campaign": result})
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
                if path == "/api/updates/install-latest":
                    # The host user asked to install now: do not require 10 idle minutes.
                    return self.reply(self.server.release_watcher.install_latest_now())
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
                if path.startswith('/api/characters/') and '/spells/' in path:
                    parts=path.split('/')
                    if len(parts) not in (6,7) or parts[4]!='spells':return self.reply({'error':'Not found'},404)
                    ch=engine.get_character(con,parts[3]);spell=artwork.find_spell(ch['profile'],parts[5])
                    if len(parts)==7 and parts[6]=='generate':
                        body=self.json_body()
                        return self.reply(artwork.generate_spell_job(DB_PATH,spell,str(body.get('checkpoint',''))),202)
                    if len(parts)==7 and parts[6]=='image':
                        raw=self.read_body(artwork.MAX_IMAGE_BYTES)
                        artwork.save_spell_image(DB_PATH,spell['id'],raw)
                        return self.reply({'ok':True,'url':'/api/spell-images/'+spell['id']})
                    return self.reply({'error':'Not found'},404)
                if path.startswith('/api/characters/') and path.endswith('/portrait'):
                    parts=path.split('/')
                    if len(parts)!=5:return self.reply({'error':'Not found'},404)
                    char=engine.get_character(con,parts[3])
                    raw=self.read_body(artwork.MAX_IMAGE_BYTES)
                    artwork.save_portrait(DB_PATH,char['id'],raw)
                    # Existing campaigns keep their current portrait unless edited there.
                    return self.reply({'ok':True,'url':'/api/characters/'+char['id']+'/portrait'})
                if path == '/api/characters':
                    return self.reply({'character':engine.create_character(con,self.json_body())},201)
                if path.startswith('/api/campaigns/') and path.endswith('/portrait'):
                    parts=path.split('/')
                    if len(parts)!=5: return self.reply({'error':'Not found'},404)
                    campaign=engine.get_campaign(con,parts[3])
                    raw=self.read_body(artwork.MAX_IMAGE_BYTES)
                    artwork.save_portrait(DB_PATH,campaign['id'],raw)
                    if campaign.get('character_id'):
                        artwork.save_portrait(DB_PATH,campaign['character_id'],raw)
                    return self.reply({'ok':True,'url':'/api/artwork/portraits/'+campaign['id']})
                if path.startswith('/api/campaigns/') and path.endswith('/portrait/generate'):
                    parts=path.split('/')
                    if len(parts)!=6: return self.reply({'error':'Not found'},404)
                    campaign=engine.get_campaign(con,parts[3]);world=engine.get_world(con,campaign['world_id'])
                    info=self.json_body()
                    return self.reply(artwork.start_job(DB_PATH,'portrait',campaign,world,
                        str(info.get('checkpoint','')),refresh=True),202)
                if path == '/api/artwork/generate-scene':
                    info=self.json_body()
                    campaign=engine.get_campaign(con,str(info.get('campaign_id','')))
                    world=engine.get_world(con,campaign['world_id'])
                    messages=engine.get_messages(con,campaign['id'])
                    last=next((m['content'] for m in reversed(messages) if m['role']=='gm'),'')
                    return self.reply(artwork.start_job(DB_PATH,'scene',campaign,world,
                        str(info.get('checkpoint','')),excerpt=last,refresh=bool(info.get('refresh'))),202)
                if path == '/api/artwork/lock-scene':
                    info=self.json_body()
                    campaign=engine.get_campaign(con,str(info.get('campaign_id','')))
                    if type(info.get('locked')) is not bool: raise ValueError('locked must be true or false')
                    return self.reply({'scene':artwork.lock_scene(con,campaign['world_id'],
                        campaign['state'].get('location','Unknown'),info['locked'],DB_PATH)})
                if path == '/api/lore/discover':
                    payload=self.json_body()
                    return self.reply(lore.discover(str(payload.get('query','')),str(payload.get('related',''))))
                if path == '/api/lore/import':
                    payload=self.json_body()
                    sections=lore.as_sections(payload.get('entries',[]))
                    world_id=str(payload.get('world_id') or '')
                    if world_id:
                        return self.reply({'world':engine.append_world_lore(con,world_id,sections)})
                    title=engine.clean(payload.get('title'),150)
                    if not title:raise ValueError('Enter a world name')
                    world=engine.make_world(con,{'title':title,'author':'Community lore references (Wikipedia)',
                      'description':engine.clean(payload.get('description'),2400) or 'Setting reference imported from Wikipedia, with source attribution.',
                      'sections':sections})
                    return self.reply({'world':world},201)
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

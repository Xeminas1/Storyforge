"""Local media for Storyforge. Creator images never leave the machine unless an
explicitly configured local ComfyUI instance is asked to generate artwork.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sqlite3
import threading
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MAX_IMAGE_BYTES = 8 * 1024 * 1024
JOBS: dict[str, dict] = {}
JOB_LOCK = threading.RLock()


def image_type(raw: bytes) -> str:
    if len(raw) > MAX_IMAGE_BYTES or len(raw) < 20:
        raise ValueError('Image must be smaller than 8 MB')
    if raw.startswith(b'\x89PNG\r\n\x1a\n') and raw[12:16] == b'IHDR':
        return 'png'
    if raw[:3] == b'\xff\xd8\xff' and raw[-2:] == b'\xff\xd9':
        return 'jpg'
    if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        return 'webp'
    raise ValueError('Upload a valid PNG, JPEG or WebP image')


def asset_dir(db_path: Path) -> Path:
    path = Path(db_path).parent / 'artwork'
    path.mkdir(parents=True, exist_ok=True)
    return path


def character_file(db_path: Path, campaign_id: str) -> Path | None:
    for ext in ('png', 'jpg', 'webp'):
        path = asset_dir(db_path) / 'portraits' / f'{campaign_id}.{ext}'
        if path.is_file():
            return path
    return None


def save_portrait(db_path: Path, campaign_id: str, raw: bytes) -> Path:
    kind = image_type(raw)
    base = asset_dir(db_path) / 'portraits'
    base.mkdir(parents=True, exist_ok=True)
    new_file = base / f'{campaign_id}.{kind}'
    temp = base / f'{campaign_id}.{kind}.tmp'
    temp.write_bytes(raw)
    os.replace(temp, new_file)
    for ext in ('png', 'jpg', 'webp'):
        old = base / f'{campaign_id}.{ext}'
        if old != new_file:
            old.unlink(missing_ok=True)
    return new_file


def scene_key(world_id: str, location: str) -> str:
    return hashlib.sha256((world_id + '\0' + location.strip().casefold()).encode()).hexdigest()[:32]


def prepare_db(con: sqlite3.Connection) -> None:
    con.execute('''CREATE TABLE IF NOT EXISTS scene_art (
      world_id TEXT NOT NULL REFERENCES worlds(id),
      scene_key TEXT NOT NULL, location TEXT NOT NULL,
      filename TEXT NOT NULL, locked INTEGER NOT NULL DEFAULT 0,
      prompt TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (world_id, scene_key))''')
    con.commit()


def scene_record(con: sqlite3.Connection, world_id: str, location: str, db_path: Path) -> dict:
    prepare_db(con)
    key = scene_key(world_id, location)
    row = con.execute('SELECT * FROM scene_art WHERE world_id=? AND scene_key=?', (world_id, key)).fetchone()
    result = {'location':location,'key':key,'url':None,'locked':False,'prompt':''}
    if row:
        result['locked'] = bool(row['locked'])
        result['prompt'] = row['prompt']
        if (asset_dir(db_path) / 'scenes' / row['filename']).is_file():
            result['url'] = '/api/artwork/scenes/' + world_id + '/' + key
    with JOB_LOCK:
        job = JOBS.get('scene:' + world_id + ':' + key)
        result['job'] = dict(job) if job else None
    return result


def scene_file(con: sqlite3.Connection, world_id: str, key: str, db_path: Path) -> Path | None:
    prepare_db(con)
    row = con.execute('SELECT filename FROM scene_art WHERE world_id=? AND scene_key=?', (world_id,key)).fetchone()
    if not row: return None
    path = asset_dir(db_path) / 'scenes' / row['filename']
    return path if path.is_file() else None


def lock_scene(con: sqlite3.Connection, world_id: str, location: str, locked: bool, db_path: Path) -> dict:
    current = scene_record(con, world_id, location, db_path)
    if not current['url']:
        raise ValueError('Generate a scene image before locking it')
    con.execute('UPDATE scene_art SET locked=? WHERE world_id=? AND scene_key=?',
                (int(bool(locked)),world_id,current['key']))
    con.commit()
    return scene_record(con, world_id, location, db_path)


def comfy_base() -> str:
    # Deliberately pinned to localhost: never use arbitrary user-controlled URLs.
    port = int(os.environ.get('STORYFORGE_COMFY_PORT', '8188'))
    if not (1 <= port <= 65535):
        raise ValueError('Invalid local ComfyUI port')
    return f'http://127.0.0.1:{port}'


def comfy_request(path: str, payload: dict | None = None, timeout=12) -> bytes:
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(comfy_base() + path, data=data,
                  headers={'Content-Type':'application/json'} if data is not None else {})
    with urlopen(req, timeout=timeout) as response:
        if response.status >= 400: raise RuntimeError(f'ComfyUI HTTP {response.status}')
        return response.read(18 * 1024 * 1024)


def comfy_checkpoints() -> list[str]:
    try:
        data = json.loads(comfy_request('/object_info/CheckpointLoaderSimple'))
        return data['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0][:100]
    except Exception:
        return []


def comfy_status() -> dict:
    try:
        with urlopen(comfy_base() + '/system_stats', timeout=2) as response:
            available = response.status == 200
    except Exception:
        available = False
    return {'available': available, 'checkpoints':comfy_checkpoints() if available else [],
            'engine':'Local ComfyUI', 'port':int(comfy_base().rsplit(':',1)[1])}


def workflow(prompt: str, checkpoint: str, width: int, height: int) -> dict:
    # ComfyUI default text-to-image graph; a local checkpoint must be installed.
    negative = 'low quality, blurry, text, watermark, logo, letters, signature, collage, frame'
    return {
      '1':{'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':checkpoint}},
      '2':{'class_type':'EmptyLatentImage','inputs':{'width':width,'height':height,'batch_size':1}},
      '3':{'class_type':'CLIPTextEncode','inputs':{'text':prompt,'clip':['1',1]}},
      '4':{'class_type':'CLIPTextEncode','inputs':{'text':negative,'clip':['1',1]}},
      '5':{'class_type':'KSampler','inputs':{'seed':random.SystemRandom().randrange(1,2**52),
         'steps':24,'cfg':7,'sampler_name':'euler','scheduler':'normal','denoise':1,
         'model':['1',0],'positive':['3',0],'negative':['4',0],'latent_image':['2',0]}},
      '6':{'class_type':'VAEDecode','inputs':{'samples':['5',0],'vae':['1',2]}},
      '7':{'class_type':'SaveImage','inputs':{'filename_prefix':'Storyforge','images':['6',0]}}
    }


def generate(prompt: str, checkpoint: str, portrait=False) -> bytes:
    width,height = (640,896) if portrait else (1024,576)
    answer=json.loads(comfy_request('/prompt',{'prompt':workflow(prompt,checkpoint,width,height)},30))
    prompt_id=answer.get('prompt_id')
    if not isinstance(prompt_id,str) or not re.fullmatch(r'[a-fA-F0-9-]{16,64}', prompt_id):
        raise RuntimeError('ComfyUI did not accept the requested checkpoint/workflow')
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        time.sleep(2)
        history=json.loads(comfy_request('/history/'+prompt_id,timeout=15))
        entry=history.get(prompt_id,{})
        if entry.get('status',{}).get('status_str')=='error':
            raise RuntimeError('ComfyUI failed to generate the image')
        outputs=entry.get('outputs',{}).get('7',{}).get('images',[])
        if outputs:
            img=outputs[0]
            data=comfy_request('/view?'+urlencode({'filename':img['filename'],
                'subfolder':img.get('subfolder',''),'type':img.get('type','output')}),timeout=20)
            image_type(data)
            return data
    raise TimeoutError('Image generation timed out; ComfyUI may still be working')


def scene_prompt(world: dict, location: str, excerpt: str) -> str:
    return (f'Wide cinematic environmental concept art for a fantasy interactive story. '
            f'World: {world["title"][:150]}. Location: {location[:200]}. '
            f'World atmosphere: {world.get("description", "")[:700]}. '
            f'Location and recent storytelling details: {excerpt[-900:]}. '
            'No characters in the foreground, no captions or lettering, richly detailed architecture, '
            'cohesive worldbuilding, painterly dark fantasy illustration, dramatic volumetric lighting.')[:2200]


def portrait_prompt(campaign: dict) -> str:
    pc=campaign['pc_profile']
    return (f'Character portrait, high quality fantasy RPG painted illustration. '
            f'Name: {campaign["pc_name"]}. Race: {pc.get("species","")}. '
            f'Role: {pc.get("role","")}. Visual appearance: {pc.get("appearance","")[:1500]}. '
            f'Manner and expression: {pc.get("personality","")[:400]}. '
            'Single character, waist-up, painterly realism, dark painterly background, '
            'no captions, no logos, anatomically coherent.')[:2400]


def start_job(db_path: Path, kind: str, campaign: dict, world: dict, checkpoint: str,
              excerpt: str='', refresh=False) -> dict:
    if not checkpoint or checkpoint not in comfy_checkpoints():
        raise ValueError('Choose a checkpoint installed in your local ComfyUI')
    if kind not in ('scene','portrait'): raise ValueError('Unknown artwork kind')
    location=(campaign['state'].get('location') or 'Unknown')[:220]
    key=scene_key(world['id'],location)
    token = f'scene:{world["id"]}:{key}' if kind=='scene' else f'portrait:{campaign["id"]}'
    import engine
    with engine.open_db(db_path) as con:
        if kind=='scene':
            record=scene_record(con,world['id'],location,db_path)
            if record['locked']: raise ValueError('Unlock this image before replacing it')
            if record['url'] and not refresh: return {'status':'ready','url':record['url']}
    with JOB_LOCK:
        if JOBS.get(token,{}).get('status')=='generating':
            return dict(JOBS[token])
        JOBS[token]={'status':'generating','kind':kind,'error':''}

    def run():
        try:
            prompt = portrait_prompt(campaign) if kind=='portrait' else scene_prompt(world,location,excerpt)
            raw=generate(prompt,checkpoint,portrait=(kind=='portrait'))
            if kind=='portrait':
                save_portrait(db_path,campaign['id'],raw)
            else:
                base=asset_dir(db_path)/'scenes';base.mkdir(parents=True,exist_ok=True)
                filename=key+'.png'
                tmp=base/(filename+'.tmp');tmp.write_bytes(raw);os.replace(tmp,base/filename)
                with engine.open_db(db_path) as con:
                    prepare_db(con)
                    con.execute('''INSERT INTO scene_art(world_id,scene_key,location,filename,prompt)
                      VALUES(?,?,?,?,?) ON CONFLICT(world_id,scene_key) DO UPDATE SET
                      filename=excluded.filename,prompt=excluded.prompt,updated_at=CURRENT_TIMESTAMP''',
                      (world['id'],key,location,filename,prompt))
                    con.commit()
            with JOB_LOCK: JOBS[token]={'status':'ready','kind':kind,'error':''}
        except Exception as exc:
            with JOB_LOCK: JOBS[token]={'status':'failed','kind':kind,'error':str(exc)[:250]}
    threading.Thread(target=run,daemon=True,name='storyforge-artwork').start()
    return {'status':'generating','kind':kind}


def job_status(kind: str, campaign: dict) -> dict | None:
    if kind=='portrait': token='portrait:'+campaign['id']
    else: token='scene:'+campaign['world_id']+':'+scene_key(campaign['world_id'],campaign['state'].get('location','Unknown'))
    with JOB_LOCK:
        return dict(JOBS[token]) if token in JOBS else None

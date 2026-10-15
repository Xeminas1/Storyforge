"""Build Storyforge release ZIP with a verifiable per-file checksum manifest."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import updater


def build(version: str, output: Path) -> Path:
    if version != updater.VERSION:
        raise ValueError(f'Updater code says {updater.VERSION}; refused manifest version {version}')
    paths = ['server.py', 'engine.py', 'narration.py', 'artwork.py', 'updater.py', 'README.md']
    paths += [p.relative_to(ROOT).as_posix() for folder in ('static', 'tests', 'tools') for p in (ROOT/folder).iterdir()
              if p.is_file() and updater.installable(p.relative_to(ROOT).as_posix())]
    paths = sorted(set(paths))
    contents = {p: (ROOT/p).read_bytes() for p in paths}
    checksums = {p: hashlib.sha256(c).hexdigest() for p,c in contents.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for p, data in contents.items():
            archive.writestr('Storyforge/' + p, data)
        archive.writestr('Storyforge/update-manifest.json', json.dumps({
            'version': version, 'files': checksums}, sort_keys=True, indent=2))
    return output


if __name__=='__main__':
    if len(sys.argv)<2:
        raise SystemExit('Usage: python tools/build_release.py X.Y.Z [output.zip]')
    version=sys.argv[1]
    output=Path(sys.argv[2]) if len(sys.argv)>=3 else ROOT.parent/(f'Storyforge_v{version}.zip')
    print(build(version, output))

"""Verify delivered source bytes before development; Python standard library only."""
from pathlib import Path,PurePosixPath
import hashlib
import json
import sys


def safe_name(name):
    if not isinstance(name,str) or '\\' in name or ':' in name:return False
    path=PurePosixPath(name)
    return bool(name) and not path.is_absolute() and all(part not in ('..','.git','.venv') for part in path.parts) and str(path)==name and name not in ('.','HANDOFF-MANIFEST.json')


def verify(root):
    root=Path(root).resolve()
    manifest=json.loads((root/'HANDOFF-MANIFEST.json').read_text(encoding='utf-8'))
    if manifest.get('format_version')!=1 or not isinstance(manifest.get('files'),dict):raise ValueError('Unknown manifest format')
    required={'00_START_HERE.md','AGENTS.md','PROMPT_CODEX.md','PROJECT_STATUS.json','jarvis/main.py','requirements.txt'}
    if not required.issubset(manifest['files']):raise ValueError('Incomplete project manifest')
    failures=[]
    for name,metadata in manifest['files'].items():
        if not safe_name(name):raise ValueError('Unsafe manifest path')
        path=root/name
        if any(item.is_symlink() for item in (path,*path.parents) if item!=root.parent):
            raise ValueError('Symlink is not a delivered source file')
        if not path.is_file():failures.append(name+': missing');continue
        raw=path.read_bytes()
        if len(raw)!=metadata['size_bytes'] or hashlib.sha256(raw).hexdigest()!=metadata['sha256']:failures.append(name+': changed')
    if failures:raise ValueError('Delivery differs: '+', '.join(failures))
    return manifest


def main():
    try:
        manifest=verify(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parents[1])
    except (ValueError,OSError,KeyError,TypeError) as exc:raise SystemExit(str(exc))
    print(f"Verified {len(manifest['files'])} delivered files; source commit {manifest['source_commit']}")
    print('Checksums describe this delivery, not authenticity or future edited files.')

if __name__=='__main__':main()

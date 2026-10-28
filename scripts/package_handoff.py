"""Build a flat source ZIP from a clean git checkout, with per-file checksums."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


def build(root,output):
    def git(*args):return subprocess.check_output(['git',*args],cwd=root)
    if git('status','--porcelain').strip():raise ValueError('Commit the intended source first; checkout must be clean')
    commit=git('rev-parse','HEAD').decode().strip()
    names=git('ls-files','-z').decode().strip('\0').split('\0')
    blobs={}
    for name in names:
        if name=='HANDOFF-MANIFEST.json':continue  # Regenerate; never checksum a previous manifest.
        path=root/name
        if path.is_symlink():raise ValueError('Symlink not supported: '+name)
        parts=Path(name).parts
        if any(part in ('.git','.venv','__pycache__','.pytest_cache') for part in parts) or name=='.env' or name.endswith(('.db','.sqlite3','.pyc')):
            raise ValueError('Runtime/private file is tracked: '+name)
        if name.startswith('data/') and name!='data/.gitkeep':raise ValueError('Database directory must not be packaged')
        blobs[name]=path.read_bytes()
    status=json.loads(blobs['PROJECT_STATUS.json'])
    manifest={'format_version':1,'application_version':status['application_version'],
              'handoff_revision':status['handoff_revision'],'source_commit':commit,
              'files':{name:{'size_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in sorted(blobs.items())}}
    output=Path(output).resolve()
    if output.is_relative_to(root):raise ValueError('Keep generated ZIP outside the source checkout')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        first=['00_START_HERE.md','PROMPT_CODEX.md','AGENTS.md','PROJECT_STATUS.json']
        for name in first+[name for name in sorted(blobs) if name not in first]:archive.writestr(name,blobs[name])
        archive.writestr('HANDOFF-MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(f'Created {output.name}: {len(blobs)} source files + manifest; {commit}')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:build(Path(__file__).resolve().parents[1],args.output)
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:raise SystemExit(str(exc))

if __name__=='__main__':main()

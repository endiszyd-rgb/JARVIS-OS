"""Create an offline read snapshot from an explicitly selected local AutoLogika DB."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jarvis.workshop import build_snapshot

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Copy AutoLogika via SQLite read-only backup; never migrate or write source records')
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--destination',type=Path,default=Path('data/autologika/workshop.snapshot.sqlite3'))
    args=parser.parse_args()
    print(json.dumps(build_snapshot(args.source,args.destination),indent=2))

"""Export the previous unassigned database to a backup without modifying it."""
import json
import sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
source=ROOT/'data'/'motionai.sqlite'
if not source.is_file():raise SystemExit('No older unassigned database found.')
with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as db:
    names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    sessions=[json.loads(r[0]) for r in db.execute('SELECT payload FROM sessions')] if 'sessions' in names else []
    routines=[json.loads(r[0]) for r in db.execute('SELECT payload FROM routines')] if 'routines' in names else []
target=ROOT/'data'/'legacy-recordings-backup.json'
if target.exists():raise SystemExit('A legacy backup already exists; keep it or rename it before exporting again.')
target.write_text(json.dumps({'format':'motionai-backup','version':2,'sessions':sessions,'routines':routines},allow_nan=False),encoding='utf-8')
print(f'Exported {len(sessions)} recordings and {len(routines)} routines to {target}')

"""Initialise mounted storage, then drop container root privileges before serving."""
import os
from pathlib import Path

def main():
    storage=Path('/var/data')
    if os.geteuid()==0:
        storage.mkdir(parents=True,exist_ok=True)
        for folder,dirs,files in os.walk(storage,followlinks=False):
            for p in [Path(folder),*(Path(folder)/n for n in files)]:
                if not p.is_symlink():os.chown(p,10001,10001)
        os.setgroups([]);os.setgid(10001);os.setuid(10001)
    from backend.serve import main as serve
    serve()

if __name__=='__main__':main()

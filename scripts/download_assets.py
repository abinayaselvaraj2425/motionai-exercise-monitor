"""Download public camera assets; verify checksums before replacing any file."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parent.parent

def main():
    assets=json.loads((ROOT/'scripts'/'assets.json').read_text())
    for asset in assets:
        path=ROOT/'public'/asset['path']
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==asset['sha256']:
            print('Verified:',asset['path']);continue
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.download')
        with urlopen(asset['url'],timeout=120) as response,temporary.open('wb') as target:
            while chunk:=response.read(1024*1024):target.write(chunk)
        if hashlib.sha256(temporary.read_bytes()).hexdigest()!=asset['sha256']:
            temporary.unlink()
            raise RuntimeError('Asset checksum mismatch: '+asset['path'])
        temporary.replace(path)
        print('Downloaded and verified:',asset['path'])
if __name__=='__main__':main()

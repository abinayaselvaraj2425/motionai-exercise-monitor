"""Recover the official checkpoint and verify its exact SHA-256."""
import hashlib
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parent.parent
URL='https://huggingface.co/walterzhu/MotionBERT/resolve/main/checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin'
EXPECTED='9811155371db4ca5d20f31a36a232d41012e12e1333882888a564d741861148f'
path=ROOT/'models'/'motionbert'/'best_epoch.bin'
path.parent.mkdir(parents=True,exist_ok=True)
temporary=path.with_suffix('.download')
with urlopen(URL,timeout=120) as source, temporary.open('wb') as target:
    while chunk:=source.read(1024*1024):target.write(chunk)
if hashlib.sha256(temporary.read_bytes()).hexdigest()!=EXPECTED:
    temporary.unlink()
    raise RuntimeError('Checkpoint checksum does not match the verified official file.')
temporary.replace(path)
print('MotionBERT checkpoint verified. Restart the app to load it.')

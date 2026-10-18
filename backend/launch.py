"""Portable local launcher. Only the Python standard library is needed for preflight."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent.parent


def configure_local_runtime():
    """An optional development hint never overrides an installed virtual environment."""
    hint = ROOT / '.local-python-path'
    if sys.prefix != sys.base_prefix or not hint.is_file():
        return
    location = Path(hint.read_text(encoding='utf-8-sig').strip())
    if location.is_dir():
        sys.path.append(str(location))


def preflight():
    if sys.version_info < (3, 11):
        return 'Python 3.11 or newer is required. Install Python, then run INSTALL.bat.'
    missing = [name for name in ('fastapi', 'uvicorn', 'numpy') if importlib.util.find_spec(name) is None]
    if missing:
        return 'Missing Python packages: ' + ', '.join(missing) + '. Run INSTALL.bat before starting the app.'
    required = ['index.html', 'assets/app.js', 'assets/app.css',
                'mediapipe/pose_landmarker_lite.task',
                'mediapipe/wasm/vision_wasm_internal.js',
                'mediapipe/wasm/vision_wasm_internal.wasm',
                'mediapipe/wasm/vision_wasm_nosimd_internal.js',
                'mediapipe/wasm/vision_wasm_nosimd_internal.wasm']
    missing = [name for name in required if not (ROOT / 'dist' / name).is_file() or (ROOT / 'dist' / name).stat().st_size == 0]
    if missing:
        return 'The application folder is incomplete: ' + ', '.join(missing) + '. Extract the full release again, or run npm install and npm run build.'
    return None


def existing_server(port):
    """Identify our app before reusing a port occupied by another program."""
    try:
        with urlopen(f'http://127.0.0.1:{port}/api/health', timeout=2) as response:
            data = json.load(response)
            if data.get('app') == 'motionai':
                return 'motionai'
    except (URLError, ValueError, OSError):
        pass
    with socket.socket() as connection:
        connection.settimeout(.5)
        return 'occupied' if connection.connect_ex(('127.0.0.1', port)) == 0 else None


def open_when_ready(port):
    for _ in range(60):
        if existing_server(port) == 'motionai':
            webbrowser.open(f'http://localhost:{port}/')
            return
        time.sleep(.5)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Start MotionAI on this computer.')
    parser.add_argument('--port', type=int, default=int(os.environ.get('MOTIONAI_PORT', '3000')))
    parser.add_argument('--open-browser', action='store_true')
    parser.add_argument('--check', action='store_true', help='Check the installation without starting a server.')
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error('The port must be between 1024 and 65535.')
    configure_local_runtime()
    problem = preflight()
    if problem:
        print('\nMotionAI could not start.\n' + problem, file=sys.stderr)
        return 1
    if args.check:
        print('MotionAI installation is ready. Camera model and browser assets are present.')
        if importlib.util.find_spec('torch') is None:
            print('MotionBERT needs PyTorch. Run INSTALL.bat to enable saved-session 3D analysis.')
        return 0
    state = existing_server(args.port)
    if state == 'motionai':
        print(f'MotionAI is already running at http://localhost:{args.port}/')
        if args.open_browser:
            webbrowser.open(f'http://localhost:{args.port}/')
        return 0
    if state:
        print(f'Port {args.port} is in use by another program. Close that program or set MOTIONAI_PORT to a different port.', file=sys.stderr)
        return 1
    if args.open_browser:
        threading.Thread(target=open_when_ready, args=(args.port,), daemon=True).start()
    print(f'\nMotionAI: http://localhost:{args.port}/\nKeep this window open while using the app. Press Ctrl+C to stop.\n', flush=True)
    try:
        import uvicorn
        uvicorn.run('backend.submission_api:app', host='127.0.0.1', port=args.port, log_level='info')
    except (ImportError, OSError) as exc:
        print(f'MotionAI could not start: {exc}\nRun INSTALL.bat to repair missing dependencies.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

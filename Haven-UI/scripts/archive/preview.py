#!/usr/bin/env python3
"""
Preview script: optionally build the UI, start uvicorn, wait until it's ready, and open the browser to the UI.
"""
import argparse
import os
import subprocess
import sys
import time
import webbrowser

import requests


def copy_static_assets(repo_root):
    src = os.path.join(repo_root, 'Haven-UI', 'static', 'assets')
    dst = os.path.join(repo_root, 'Haven-UI', 'dist', 'assets')
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        for f in os.listdir(src):
            srcf = os.path.join(src, f)
            dstf = os.path.join(dst, f)
            try:
                with open(srcf, 'rb') as rf, open(dstf, 'wb') as wf:
                    wf.write(rf.read())
            except Exception:
                pass


def main():
    p = argparse.ArgumentParser()
    # Accept both lowercase GNU style and Windows-style parameter spellings
    p.add_argument('--build', '-Build', action='store_true', dest='build', help='npm ci && npm run build before running')
    p.add_argument('--port', '-Port', type=int, dest='port', default=8002)
    p.add_argument('--host', '-Host', type=str, dest='host', default='127.0.0.1')
    args = p.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    ui_dir = os.path.join(repo_root, 'Haven-UI')

    if args.build:
        os.chdir(ui_dir)
        print('Installing Node deps and building the UI...')
        subprocess.run(['npm', 'ci'], check=True)
        subprocess.run(['npm', 'run', 'build'], check=True)
        # copy static assets
        copy_static_assets(repo_root)

    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.join(repo_root, 'src')
    env['HAVEN_UI_DIR'] = ui_dir

    cmd = [sys.executable, '-u', '-m', 'uvicorn', 'src.control_room_api:app', '--host', args.host, '--port', str(args.port), '--log-level', 'info']
    print('Starting server: ', ' '.join(cmd))
    proc = subprocess.Popen(cmd, env=env)
    print('Started process PID:', proc.pid)
    with open(os.path.join(ui_dir, 'scripts', 'preview.pid'), 'w') as f:
        f.write(str(proc.pid))

    url = f'http://{args.host}:{args.port}/haven-ui/'
    print('Waiting for UI to be ready at', url)
    for i in range(30):
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                print('UI ready, opening browser...')
                webbrowser.open(url)
                break
        except Exception:
            time.sleep(1)
    else:
        print('Timeout waiting for UI; check logs or run the server manually.')

    print('Preview running (PID: {}). To stop:'.format(proc.pid))
    if os.name == 'nt':
        print(f'  taskkill /PID {proc.pid} /F')
    else:
        print(f'  kill {proc.pid}')


if __name__ == '__main__':
    main()

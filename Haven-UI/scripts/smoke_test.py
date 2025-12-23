#!/usr/bin/env python3
"""
Smoke test script for Haven-UI + API.
Usage: python scripts/smoke_test.py --base http://127.0.0.1:8000
"""
import argparse
import requests
import sys

def check(base, path):
    url = base.rstrip('/') + path
    try:
        r = requests.get(url, timeout=4)
        print(f"{url} -> {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"{url} -> ERROR: {e}")
        return False

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default='http://127.0.0.1:8000')
    args = p.parse_args()
    base = args.base
    ok = True
    ok &= check(base, '/api/status')
    ok &= check(base, '/api/stats')
    ok &= check(base, '/api/systems')
    # SPA may be served from /haven-ui (dist) or /haven-ui-static (prebuilt fallback)
    spa_ok = check(base, '/haven-ui')
    if not spa_ok:
        spa_ok = check(base, '/haven-ui-static/index.html')
    ok &= spa_ok
    # PWA assets
    ok &= check(base, '/haven-ui/manifest.webmanifest')
    ok &= check(base, '/haven-ui/registerSW.js')
    # Attempt admin login if env set
    import os
    admin_pw = os.environ.get('HAVEN_ADMIN_PASSWORD')
    if admin_pw:
        try:
            s = requests.Session()
            r = s.post(base + '/api/admin/login', json={'password': admin_pw}, timeout=5)
            print('Admin login ->', r.status_code)
            ok &= (r.status_code == 200 or r.status_code == 204)
        except Exception as e:
            print('Admin login -> ERROR', e)
            ok = False
    if ok:
        print('Smoke test PASSED')
        sys.exit(0)
    else:
        print('Smoke test FAILED')
        sys.exit(2)

if __name__ == '__main__':
    main()

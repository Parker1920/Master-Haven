import requests
base='http://127.0.0.1:8000'
paths=['/api/status','/api/stats','/api/systems','/haven-ui','/haven-ui/manifest.webmanifest']
paths += ['/systems','/discoveries']
for p in paths:
    try:
        r = requests.get(base+p, timeout=4)
        print(p, r.status_code)
    except Exception as e:
        print(p, 'ERROR', e)

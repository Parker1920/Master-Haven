import requests
base='http://127.0.0.1:8000'

# Check RTAI status
try:
    r = requests.get(base + '/api/rtai/status', timeout=4)
    print('/api/rtai/status ->', r.status_code, r.text)
except Exception as e:
    print('/api/rtai/status -> ERROR', e)

# Post a sample discovery to /api/discoveries
payload = {
    'system_name': 'Test System',
    'planet': 'Test Planet',
    'description': 'Integration test discovery',
}
try:
    r = requests.post(base + '/api/discoveries', json=payload, timeout=5)
    print('/api/discoveries POST ->', r.status_code, r.text)
except Exception as e:
    print('/api/discoveries POST -> ERROR', e)

# Verify data.json wrote discoveries
import os
import json
p = os.path.join('Haven-UI', 'data', 'data.json')
if os.path.exists(p):
    d = json.load(open(p, 'r', encoding='utf-8'))
    print('data.json discoveries count:', len(d.get('discoveries', [])))
else:
    print('data.json not found')

# Check logs
try:
    r = requests.get(base + '/api/logs', timeout=4)
    print('/api/logs ->', r.status_code, 'lines:', len(r.json().get('lines', [])))
except Exception as e:
    print('/api/logs -> ERROR', e)

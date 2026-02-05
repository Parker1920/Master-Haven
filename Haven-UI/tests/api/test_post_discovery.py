import requests
r = requests.post('http://127.0.0.1:8000/discoveries', json={"system_name":"TestPost","planet":"P","description":"T"})
print('status', r.status_code, 'text', r.text)
r2 = requests.post('http://127.0.0.1:8000/api/discoveries', json={"system_name":"TestPost2","planet":"P","description":"T2"})
print('status2', r2.status_code, 'text', r2.text)

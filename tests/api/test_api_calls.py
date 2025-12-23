import requests

print('RTAI status:')
print(requests.get('http://127.0.0.1:8000/api/rtai/status').text)
print('\nRTAI analyze:')
print(requests.post('http://127.0.0.1:8000/api/rtai/analyze/discoveries?limit=2').text)
print('\nKeeper Sync health:')
print(requests.get('http://127.0.0.1:8080/health').text)

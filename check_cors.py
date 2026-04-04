import requests

resp = requests.options('http://localhost:5000/admin/upload_results', headers={'Origin': '*'})
print('CORS Status:', resp.status_code)
headers = ['Access-Control-Allow-Origin', 'Access-Control-Allow-Methods', 'Access-Control-Allow-Headers']
for h in headers:
    val = resp.headers.get(h, 'NOT SET')
    print(f'{h}: {val}')

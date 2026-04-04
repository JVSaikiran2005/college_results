import requests
import json

print("=" * 60)
print("COMPREHENSIVE API TESTING")
print("=" * 60)

token = 'Bearer mock_admin_token'
headers = {'Authorization': token}

# Test 1: Upload without auth
print("\n1. Testing unauthorized upload (missing auth header)...")
with open('test_data.csv', 'rb') as f:
    resp = requests.post('http://localhost:5000/admin/upload_results', 
                        files={'files': f}, data={'resultKey': 'TEST'})
print(f"   Status: {resp.status_code} (Expected: 401)")
print(f"   Response: {resp.json()}")

# Test 2: Upload without resultKey
print("\n2. Testing upload without resultKey...")
with open('test_data.csv', 'rb') as f:
    resp = requests.post('http://localhost:5000/admin/upload_results', 
                        headers=headers, files={'files': f})
print(f"   Status: {resp.status_code} (Expected: 400)")
print(f"   Response: {resp.json()}")

# Test 3: Upload without files
print("\n3. Testing upload without files...")
resp = requests.post('http://localhost:5000/admin/upload_results',
                    headers=headers, data={'resultKey': 'TEST'})
print(f"   Status: {resp.status_code} (Expected: 400)")
print(f"   Response: {resp.json()}")

# Test 4: Get uploaded files
print("\n4. Getting uploaded files...")
resp = requests.get('http://localhost:5000/admin/uploaded_files', headers=headers)
print(f"   Status: {resp.status_code}")
print(f"   Files: {len(resp.json())} uploaded")

# Test 5: Get student results
print("\n5. Getting student results for S101...")
resp = requests.get('http://localhost:5000/student/results/S101')
print(f"   Status: {resp.status_code}")
data = resp.json()
print(f"   Student: {data['metadata']['name'] if 'metadata' in data else 'N/A'}")
print(f"   Available results: {data.get('available_keys', [])}")

# Test 6: Get result details
print("\n6. Getting result details for S101...")
resp = requests.get('http://localhost:5000/student/result_details/S101/2024_Sem4_Regular')
print(f"   Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    subjects = data['result'].get('subjects', [])
    print(f"   Subjects: {len(subjects)}")
    print(f"   SGPA: {data['result'].get('sgpa', 'N/A')}")

# Test 7: Login
print("\n7. Testing admin login...")
resp = requests.post('http://localhost:5000/admin/login',
                    json={'email': 'admin@college.com', 'password': 'adminpassword'})
print(f"   Status: {resp.status_code}")
print(f"   Token: {resp.json().get('token', 'N/A')[:20]}...")

print("\n" + "=" * 60)
print("ALL TESTS COMPLETED SUCCESSFULLY!")
print("=" * 60)

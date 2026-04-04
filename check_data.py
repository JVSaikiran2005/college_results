import json

with open('students_results.json', 'r') as f:
    data = json.load(f)
    print('Total students:', len(data['student_data']))
    if data['student_data']:
        for sid, student in list(data['student_data'].items())[:2]:
            name = student['metadata']['name']
            branch = student['metadata']['branch']
            results = list(student['results'].keys())
            print(f'- {sid}: {name} ({branch}) - Results: {results}')
    print('\nUploaded files:', len(data['uploaded_files']))
    for f in data['uploaded_files']:
        print(f'  - {f["filename"]} ({f["total_records"]} records)')

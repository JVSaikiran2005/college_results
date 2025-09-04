import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
from io import BytesIO, StringIO

app = Flask(__name__)
CORS(app)

DATA_FILE = 'students_results.json'

ADMIN_EMAIL = 'admin@college.com'
ADMIN_PASSWORD = 'adminpassword'


def load_results():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_results(results):
    with open(DATA_FILE, 'w') as f:
        json.dump(results, f, indent=4)


if not os.path.exists(DATA_FILE):
    save_results({})


@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    if data.get('email') == ADMIN_EMAIL and data.get('password') == ADMIN_PASSWORD:
        return jsonify({'message': 'Admin login successful!', 'token': 'mock_admin_token'}), 200
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/admin/upload_results', methods=['POST'])
def upload_results():
    if 'files' not in request.files:
        return jsonify({'error': 'No files part in the request'}), 400

    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No selected files'}), 400

    all_results = load_results()
    total_uploaded = 0
    messages = []

    for file in files:
        try:
            file_extension = file.filename.rsplit('.', 1)[1].lower()
            if file_extension == 'csv':
                df = pd.read_csv(StringIO(file.read().decode('utf-8')))
            elif file_extension in ['xls', 'xlsx']:
                df = pd.read_excel(BytesIO(file.read()))
            else:
                messages.append(f"Skipped {file.filename} (unsupported format).")
                continue

            # Determine type (regular or supply) from filename
            result_type = "supply" if "supply" in file.filename.lower() else "regular"

            temp_results = df.to_dict(orient='records')
            new_results_data = []

            for row in temp_results:
                student_id = str(row.get('studentId', '')).strip().upper()
                if not student_id:
                    continue

                student_entry = all_results.get(student_id, {
                    "studentId": student_id,
                    "name": row.get('name', ''),
                    "academicYear": row.get('academicYear', '')
                })

                # Build result block
                result_block = {
                    "sgpa": row.get('sgpa', 0.0),
                    "cgpa": row.get('cgpa', 0.0),
                    "subjects": []
                }

                subject_names = [col.replace('_Marks', '') for col in row if '_Marks' in col]
                for s_name in subject_names:
                    marks = row.get(f'{s_name}_Marks')
                    if marks is not None:
                        result_block['subjects'].append({"name": s_name, "marks": marks})

                if 'subjects' in row and isinstance(row['subjects'], str):
                    try:
                        parsed_subjects = json.loads(row['subjects'])
                        if isinstance(parsed_subjects, list):
                            result_block['subjects'].extend(parsed_subjects)
                    except json.JSONDecodeError:
                        pass

                # Assign to "regular" or "supply"
                student_entry[result_type] = result_block
                all_results[student_id] = student_entry
                new_results_data.append(student_entry)

            total_uploaded += len(new_results_data)
            messages.append(f"{file.filename}: {len(new_results_data)} {result_type} records uploaded.")

        except Exception as e:
            messages.append(f"{file.filename}: Error - {str(e)}")

    save_results(all_results)

    return jsonify({
        'message': f"Uploaded {total_uploaded} student results.",
        'details': messages
    }), 200


@app.route('/student/results/<string:student_id>', methods=['GET'])
def get_student_results(student_id):
    all_results = load_results()
    result = all_results.get(student_id.upper())
    if result:
        return jsonify(result), 200
    return jsonify({'error': 'No results found for this Student ID.'}), 404
@app.route('/admin/clear_results', methods=['POST'])
def clear_results():
    """
    Clears all stored student results (reset).
    """
    save_results({})  # overwrite with empty dict
    return jsonify({'message': 'All results have been deleted. You can now upload new files.'}), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)


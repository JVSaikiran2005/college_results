import os
import json
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import pandas as pd
from io import BytesIO, StringIO, TextIOWrapper
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Allow large uploads (e.g., up to 200 MB) — adjust if you want bigger/smaller limits
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 MB

DATA_FILE = 'students_results.json'
ADMIN_EMAIL = 'admin@college.com'
ADMIN_PASSWORD = 'adminpassword'
ADMIN_TOKEN = "mock_admin_token"


def load_results():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                data = json.load(f)
                if isinstance(data, dict) and 'student_data' in data:
                    return data
            except json.JSONDecodeError:
                pass
    return {'uploaded_files': [], 'student_data': {}}


def save_results(all_data):
    with open(DATA_FILE, 'w') as f:
        json.dump(all_data, f, indent=4)


# Ensure base file exists
if not os.path.exists(DATA_FILE) or not load_results().get('student_data'):
    save_results({'uploaded_files': [], 'student_data': {}})


@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    if data.get('email') == ADMIN_EMAIL and data.get('password') == ADMIN_PASSWORD:
        return jsonify({'message': 'Admin login successful!', 'token': ADMIN_TOKEN}), 200
    return jsonify({'error': 'Invalid credentials'}), 401


def check_admin_auth(req):
    token = req.headers.get("Authorization")
    return token == f"Bearer {ADMIN_TOKEN}"


@app.route('/admin/uploaded_files', methods=['GET'])
def get_uploaded_files():
    if not check_admin_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401
    all_data = load_results()
    # Return newest first (existing behavior)
    return jsonify(all_data.get('uploaded_files', [])[::-1]), 200


@app.route('/admin/upload_results', methods=['POST'])
def upload_results():
    if not check_admin_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401

    result_key = request.form.get('resultKey', '').strip()
    if not result_key:
        return jsonify({'error': 'Missing required form field: resultKey (e.g., 2024_Sem4_Regular)'}), 400

    if 'files' not in request.files:
        return jsonify({'error': 'No files part in the request'}), 400

    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No selected files'}), 400

    all_data = load_results()
    all_results = all_data['student_data']
    uploaded_files_list = all_data['uploaded_files']

    total_uploaded = 0
    messages = []

    for file in files:
        filename = file.filename
        try:
            if '.' not in filename:
                messages.append(f"Skipped {filename} (no extension).")
                continue
            file_extension = filename.rsplit('.', 1)[1].lower()

            # Read CSV more memory-efficiently where possible using the file stream
            if file_extension == 'csv':
                # Use TextIOWrapper on file.stream so pandas can stream-read if needed
                text_stream = TextIOWrapper(file.stream, encoding='utf-8', errors='replace')
                df = pd.read_csv(text_stream)
            elif file_extension in ['xls', 'xlsx']:
                # For Excel, read into BytesIO (pandas needs bytes)
                content = file.read()
                df = pd.read_excel(BytesIO(content))
            else:
                messages.append(f"Skipped {filename} (unsupported format).")
                continue

            temp_results = df.to_dict(orient='records')
            new_records_count = 0

            file_metadata = {
                "result_key": result_key,
                "filename": filename,
                "upload_time": datetime.now().isoformat(),
                "total_records": 0,
                "file_extension": file_extension
            }

            for row in temp_results:
                # Expect column names like: studentId, name, branch, semester, sgpa, cgpa, Subject1_Credits, Subject1_Grade, Subject1_Points, ...
                student_id = str(row.get('studentId', '')).strip().upper()
                if not student_id:
                    continue

                student_entry = all_results.get(student_id, {
                    "metadata": {
                        "studentId": student_id,
                        "name": row.get('name', ''),
                        "branch": row.get('branch', '')
                    },
                    "results": {}
                })

                semester_key = str(row.get('semester', 'N/A')).strip()

                result_block = {
                    "result_key": result_key,
                    "semester": semester_key,
                    "sgpa": row.get('sgpa', 0.0),
                    "cgpa": row.get('cgpa', 0.0),
                    "subjects": []
                }

                # Build subjects from column naming convention
                subject_data = {}
                for col, value in row.items():
                    if not isinstance(col, str):
                        continue
                    if col.endswith('_Credits'):
                        subject_name = col[:-8]
                        subject_data.setdefault(subject_name, {})['credits'] = value
                    elif col.endswith('_Grade'):
                        subject_name = col[:-6]
                        subject_data.setdefault(subject_name, {})['grade'] = value
                    elif col.endswith('_Points'):
                        subject_name = col[:-7]
                        subject_data.setdefault(subject_name, {})['points'] = value

                for subject_name, sdata in subject_data.items():
                    try:
                        credit_val = int(sdata.get("credits", 0))
                    except Exception:
                        # If credits are float-like or missing, coerce to int fallback 0
                        try:
                            credit_val = int(float(sdata.get("credits", 0)))
                        except Exception:
                            credit_val = 0
                    result_block['subjects'].append({
                        "name": subject_name,
                        "credit": credit_val,
                        "grade": sdata.get("grade", "N/A"),
                        "gradePoints": sdata.get("points", 0)
                    })

                # Insert or overwrite the result_key for this student
                student_entry['results'][result_key] = result_block
                # Update metadata if available
                if row.get('name'):
                    student_entry['metadata']['name'] = row.get('name')
                if row.get('branch'):
                    student_entry['metadata']['branch'] = row.get('branch')

                all_results[student_id] = student_entry
                new_records_count += 1

            total_uploaded += new_records_count
            file_metadata['total_records'] = new_records_count
            uploaded_files_list.append(file_metadata)
            messages.append(f"{filename} ({result_key}): {new_records_count} records processed.")

        except Exception as e:
            messages.append(f"{filename} ({result_key}): Error - {str(e)}")

    save_results(all_data)
    return jsonify({
        'message': f"Uploaded {total_uploaded} student result blocks under key '{result_key}'.",
        'details': messages
    }), 200


@app.route('/admin/delete_file', methods=['DELETE'])
def delete_uploaded_file():
    """
    Delete a single uploaded file record (and associated result key).
    Query parameters expected: result_key and filename
    Example: DELETE /admin/delete_file?result_key=2024_Sem4_Regular&filename=results.csv
    """
    if not check_admin_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401

    result_key = request.args.get('result_key', '').strip()
    filename = request.args.get('filename', '').strip()

    if not result_key or not filename:
        return jsonify({'error': 'Missing required parameters: result_key and filename'}), 400

    all_data = load_results()
    uploaded_files = all_data.get('uploaded_files', [])
    initial_count = len(uploaded_files)

    # Remove matching metadata entries (there may be duplicates; remove only exact match)
    uploaded_files = [f for f in uploaded_files if not (f.get('result_key') == result_key and f.get('filename') == filename)]
    removed_count = initial_count - len(uploaded_files)

    if removed_count == 0:
        return jsonify({'error': 'No matching uploaded file found.'}), 404

    # Persist metadata change
    all_data['uploaded_files'] = uploaded_files

    # Remove the result_key from all student records.
    # Note: Because results are keyed by result_key, removing one file with result_key will remove that key's results.
    # (If you had multiple files under same result_key, deleting one will also remove the results; that's a limitation
    #  because original file contents are not retained server-side.)
    student_data = all_data.get('student_data', {})
    affected_students = 0
    for sid, sdata in list(student_data.items()):
        if result_key in sdata.get('results', {}):
            sdata['results'].pop(result_key, None)
            affected_students += 1
            # Optionally remove student if no results left — keep metadata for audit; we will keep the student entry
    # Persist final data
    save_results(all_data)
    return jsonify({
        'message': f"Deleted file record '{filename}' under key '{result_key}'.",
        'removed_file_records': removed_count,
        'affected_student_entries': affected_students
    }), 200


@app.route('/admin/clear_results', methods=['POST'])
def clear_results():
    if not check_admin_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401
    save_results({'uploaded_files': [], 'student_data': {}})
    return jsonify({'message': 'All results and uploaded file records have been deleted.'}), 200


@app.route('/student/results/<string:student_id>', methods=['GET'])
def get_student_results_summary(student_id):
    all_data = load_results()
    student = all_data['student_data'].get(student_id.upper())
    if student:
        result_keys = list(student.get('results', {}).keys())
        default_key = sorted(result_keys)[-1] if result_keys else None
        return jsonify({
            'metadata': student.get('metadata', {}),
            'available_keys': result_keys,
            'default_key': default_key
        }), 200
    return jsonify({'error': 'No results found for this Student ID.'}), 404


@app.route('/student/result_details/<string:student_id>/<string:result_key>', methods=['GET'])
def get_student_result_details(student_id, result_key):
    all_data = load_results()
    student = all_data['student_data'].get(student_id.upper())
    if student:
        result_details = student.get('results', {}).get(result_key)
        if result_details:
            clean_result = json.loads(json.dumps(result_details, default=str))
            return jsonify({
                "metadata": student.get('metadata', {}),
                "result": clean_result
            }), 200
        return jsonify({'error': f'No results found for key \"{result_key}\".'}), 404
    return jsonify({'error': 'No student found with this ID.'}), 404


@app.route('/student/download/<string:student_id>/<string:result_key>', methods=['GET'])
def download_marksheet(student_id, result_key):
    all_data = load_results()
    student = all_data['student_data'].get(student_id.upper())

    if not student:
        return jsonify({'error': 'No results found for this Student ID.'}), 404

    result = student.get('results', {}).get(result_key)
    if not result:
        return jsonify({'error': f'No result found for key \"{result_key}\".'}), 404

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Header
    logo_path = "gvplogo.png"
    if os.path.exists(logo_path):
        try:
            c.drawImage(logo_path, 40, height - 110, width=70, height=70, preserveAspectRatio=True, mask='auto')
        except Exception:
            # ignore logo drawing errors
            pass

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, height - 60, "GAYATRI VIDYA PARISHAD")
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width/2, height - 80, "COLLEGE FOR DEGREE AND P.G. COURSES (AUTONOMOUS)")
    c.setFont("Helvetica", 10)
    c.drawCentredString(width/2, height - 95, "Affiliated to Andhra University | Accredited by NAAC with B++ Grade")
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width/2, height - 110, "OFFICIAL MEMORANDUM SEMESTER END GRADE CARD")

    y = height - 150
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Register No: {student['metadata'].get('studentId', '')}")
    c.drawString(300, y, f"Month & Year: {datetime.now().strftime('%b-%Y')}")
    y -= 15
    c.drawString(50, y, f"Branch: {student['metadata'].get('branch', '')}")
    c.drawString(300, y, f"Semester: {result.get('semester', '')}")
    y -= 15
    c.drawString(50, y, f"Name of the Candidate: {student['metadata'].get('name', '')}")
    y -= 25
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "The following Grades were secured by the Candidate")

    # Main Table
    data = [["NAME OF THE SUBJECT", "CREDITS", "GRADE", "GRADE POINTS"]]
    for subj in result.get("subjects", []):
        data.append([
            subj.get("name", ""),
            str(subj.get("credit", "")),
            subj.get("grade", ""),
            str(subj.get("gradePoints", ""))
        ])

    min_rows = 15
    while len(data) < min_rows:
        if len(data) == len(result.get("subjects", [])) + 1:
            data.append(["---oo0oo---", "", "", ""])
        else:
            data.append(["", "", "", ""])

    table = Table(data, colWidths=[250, 70, 70, 100], rowHeights=20)
    table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('GRID', (0, 0), (-1, len(result.get("subjects", []))), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))

    table_height = len(data) * 20
    table_y = y - table_height - 10
    table.wrapOn(c, width, height)
    table.drawOn(c, 50, table_y)

    spacing_after_table = 40
    cgpa_y = table_y - spacing_after_table

    cgp_data = [[f"CGPA {result.get('cgpa', 'N/A')}", f"SGPA {result.get('sgpa', 'N/A')}"]]
    cgp_table = Table(cgp_data, colWidths=[(width - 100) / 2] * 2)
    cgp_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    cgp_table.wrapOn(c, width, height)
    cgp_table.drawOn(c, 50, cgpa_y)

    footer_y = cgpa_y - 60

    grade_data = [
        ["% of Marks", "90%-100%", "80%-<90%", "70%-<80%", "60%-<70%", "50%-<60%", "40%-<50%", "0%-<40%", "Absent"],
        ["Grade", "A+", "A", "B", "C", "D", "E", "F", "AB"],
        ["Points", "10", "9", "8", "7", "6", "5", "0", "0"]
    ]
    grade_table = Table(grade_data)
    grade_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    grade_table.wrapOn(c, width, height)
    grade_table.drawOn(c, 50, footer_y)

    c.save()
    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={student_id}_{result_key}_marksheet.pdf'
    return response


if __name__ == '__main__':
    app.run(debug=True, port=5000)






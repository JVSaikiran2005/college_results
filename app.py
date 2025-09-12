import os
import json
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import pandas as pd
from io import BytesIO, StringIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from datetime import datetime

app = Flask(__name__)
CORS(app)

DATA_FILE = 'students_results.json'
ADMIN_EMAIL = 'admin@college.com'
ADMIN_PASSWORD = 'adminpassword'
ADMIN_TOKEN = "mock_admin_token"

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
        return jsonify({'message': 'Admin login successful!', 'token': ADMIN_TOKEN}), 200
    return jsonify({'error': 'Invalid credentials'}), 401

def check_admin_auth(req):
    token = req.headers.get("Authorization")
    return token == f"Bearer {ADMIN_TOKEN}"

@app.route('/admin/upload_results', methods=['POST'])
def upload_results():
    if not check_admin_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401

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
                    "branch": row.get('branch', ''),      # ✅ NEW
                    "semester": row.get('semester', '')
                })

                result_block = {
                    "sgpa": row.get('sgpa', 0.0),
                    "cgpa": row.get('cgpa', 0.0),
                    "subjects": []
                }
                
                # Corrected logic to parse subject data
                subject_data = {}
                for col, value in row.items():
                    if '_Credits' in col:
                        subject_name = col.replace('_Credits', '')
                        if subject_name not in subject_data:
                            subject_data[subject_name] = {}
                        subject_data[subject_name]['credits'] = value
                    elif '_Grade' in col:
                        subject_name = col.replace('_Grade', '')
                        if subject_name not in subject_data:
                            subject_data[subject_name] = {}
                        subject_data[subject_name]['grade'] = value
                    elif '_Points' in col:
                        subject_name = col.replace('_Points', '')
                        if subject_name not in subject_data:
                            subject_data[subject_name] = {}
                        subject_data[subject_name]['points'] = value

                for subject_name, sdata in subject_data.items():
                                 result_block['subjects'].append({
                                    "name": subject_name,
                                    "credit": int(sdata.get("credits", 0)),
                                    "grade": sdata.get("grade", "N/A"),
                                    "gradePoints": sdata.get("points", 0)
                            })
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
    print("DEBUG RESULT:", result)   # log to console
    if result:
        # Replace NaN/None with "N/A"
        clean_result = json.loads(json.dumps(result, default=str))
        return jsonify(clean_result), 200
    return jsonify({'error': 'No results found for this Student ID.'}), 404


@app.route('/admin/clear_results', methods=['POST'])
def clear_results():
    if not check_admin_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401
    save_results({})
    return jsonify({'message': 'All results have been deleted. You can now upload new files.'}), 200

@app.route('/student/download/<string:student_id>/<string:result_type>', methods=['GET'])
def download_marksheet(student_id, result_type):
    all_results = load_results()
    student = all_results.get(student_id.upper())

    if not student:
        return jsonify({'error': 'No results found for this Student ID.'}), 404
    if result_type not in student:
        return jsonify({'error': f'No {result_type} results found.'}), 404

    result = student[result_type]

    # Create PDF in memory
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    #college logo
    logo_path = "gvplogo.png"
    if os.path.exists(logo_path):
        c.drawImage(logo_path, 40, height - 110, width=70, height=70, preserveAspectRatio=True, mask='auto')
    # College header
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, height - 60, "GAYATRI VIDYA PARISHAD")
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width/2, height - 80, "COLLEGE FOR DEGREE AND P.G. COURSES (AUTONOMOUS)")
    c.setFont("Helvetica", 10)
    c.drawCentredString(width/2, height - 95, "Affiliated to Andhra University | Accredited by NAAC with B++ Grade")
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width/2, height - 110, "ENGINEERING AND TECHNOLOGY PROGRAM")
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width/2, height - 125, "OFFICIAL MEMORANDUM OF SEMESTER-END GRADE CARD")

    # Student info
    y = height - 150
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Register No: {student.get('studentId', '')}")
    c.drawString(300, y, f"Month & Year: {datetime.now().strftime('%b-%Y')}")
    y -= 15
    c.drawString(50, y, f"Branch: {student.get('branch', '')}")
    c.drawString(300, y, f"Semester: {student.get('semester', '')}")
    y -= 15
    c.drawString(50, y, f"Name of the Candidate: {student.get('name', '')}")

    y -= 25
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "The following Grades were secured by the Candidate")

    # Table data
    y -= 30
    data = [["NAME OF THE SUBJECT", "CREDITS", "GRADE", "GRADE POINTS"]]
    for subj in result.get("subjects", []):
        data.append([
            subj.get("name", ""),
            subj.get("credit", ""),
            subj.get("grade", ""),
            subj.get("gradePoints", "")
        ])

    # Build table
    table = Table(data, colWidths=[250, 70, 70, 100])
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
    ]))
    table.wrapOn(c, width, height)
    table.drawOn(c, 50, y - len(data)*20)

    # CGPA & SGPA
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y - len(data)*20 - 30, f"CGPA {result.get('cgpa', 'N/A')}")
    c.drawString(250, y - len(data)*20 - 30, f"SGPA {result.get('sgpa', 'N/A')}")

    # Footer grading scale
    # Corrected code to display the grading scale in a table
    footer_y = 120
    grade_data = [
        ["% of Marks", "90%-100%", "80%-<90%", "70%-<80%", "60%-<70%", "50%-<60%", "40%-<50%", "0%-<40%", "Absent"],
        ["Grade", "A+", "A", "B", "C", "D", "E", "F", "AB"],
        ["Points", "10", "9", "8", "7", "6", "5", "0", "0"]
    ]
    grade_table = Table(grade_data)
    grade_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
    ]))
    grade_table.wrapOn(c, width, height)
    grade_table.drawOn(c, 50, footer_y)

    

    c.save()
    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={student_id}_{result_type}_marksheet.pdf'
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5000)



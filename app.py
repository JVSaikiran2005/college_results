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

# New data structure: {'uploaded_files': [...], 'student_data': { 'S101': { 'metadata': {...}, 'results': { 'RESULT_KEY': {...} } } } }
def load_results():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                # Load existing data or return the new default structure
                data = json.load(f)
                if isinstance(data, dict) and 'student_data' in data:
                    return data
            except json.JSONDecodeError:
                pass
    return {'uploaded_files': [], 'student_data': {}}

def save_results(all_data):
    with open(DATA_FILE, 'w') as f:
        json.dump(all_data, f, indent=4)

# Initialize file with new structure if it doesn't exist or is empty/corrupt
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
    """Admin-only endpoint to list all uploaded result files."""
    if not check_admin_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401
    
    all_data = load_results()
    # Return the file list, reverse it to show most recent first
    return jsonify(all_data.get('uploaded_files', [])[::-1]), 200

@app.route('/admin/upload_results', methods=['POST'])
def upload_results():
    if not check_admin_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Result Key is now mandatory for multi-year tracking
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
        try:
            file_extension = file.filename.rsplit('.', 1)[1].lower()
            if file_extension == 'csv':
                # Use stream to read multiple times if needed, and decode utf-8
                file_content = file.read().decode('utf-8')
                df = pd.read_csv(StringIO(file_content))
            elif file_extension in ['xls', 'xlsx']:
                df = pd.read_excel(BytesIO(file.read()))
            else:
                messages.append(f"Skipped {file.filename} (unsupported format).")
                continue

            temp_results = df.to_dict(orient='records')
            new_records_count = 0
            
            # Record metadata for the uploaded file
            file_metadata = {
                "result_key": result_key,
                "filename": file.filename,
                "upload_time": datetime.now().isoformat(),
                "total_records": 0, # Will be updated
                "file_extension": file_extension
            }

            for row in temp_results:
                student_id = str(row.get('studentId', '')).strip().upper()
                if not student_id:
                    continue

                # Get existing student entry or create a new one
                student_entry = all_results.get(student_id, {
                    "metadata": {
                        "studentId": student_id,
                        "name": row.get('name', ''),
                        "branch": row.get('branch', '')
                    },
                    "results": {}
                })
                
                # Use a specific key from the results file for semester/year, if available, otherwise default
                semester_key = str(row.get('semester', 'N/A')).strip() 

                result_block = {
                    "result_key": result_key,
                    "semester": semester_key, 
                    "sgpa": row.get('sgpa', 0.0),
                    "cgpa": row.get('cgpa', 0.0),
                    "subjects": []
                }
                
                # Logic to parse subject data (as in original file)
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
                
                # Store the result under the unique result_key
                student_entry['results'][result_key] = result_block
                all_results[student_id] = student_entry
                new_records_count += 1

            total_uploaded += new_records_count
            file_metadata['total_records'] = new_records_count
            
            # Append file metadata to the list if records were processed successfully
            uploaded_files_list.append(file_metadata)
            messages.append(f"{file.filename} ({result_key}): {new_records_count} records processed.")

        except Exception as e:
            messages.append(f"{file.filename} ({result_key}): Error - {str(e)}")

    save_results(all_data)

    return jsonify({
        'message': f"Uploaded {total_uploaded} student result blocks under key '{result_key}'.",
        'details': messages
    }), 200

@app.route('/student/results/<string:student_id>', methods=['GET'])
def get_student_results_summary(student_id):
    """Returns student metadata and a list of all available result keys."""
    all_data = load_results()
    student = all_data['student_data'].get(student_id.upper())
    
    if student:
        # Returns metadata and a list of available result keys for selection
        result_keys = list(student.get('results', {}).keys())
        
        # Determine the latest/best result key to show by default (e.g., first one alphabetically)
        default_key = sorted(result_keys)[-1] if result_keys else None 
        
        return jsonify({
            'metadata': student.get('metadata', {}),
            'available_keys': result_keys,
            'default_key': default_key
        }), 200
    return jsonify({'error': 'No results found for this Student ID.'}), 404

@app.route('/student/result_details/<string:student_id>/<string:result_key>', methods=['GET'])
def get_student_result_details(student_id, result_key):
    """Returns the details for a specific result key."""
    all_data = load_results()
    student = all_data['student_data'].get(student_id.upper())
    
    if student:
        result_details = student.get('results', {}).get(result_key)
        if result_details:
            # Replace NaN/None with "N/A"
            clean_result = json.loads(json.dumps(result_details, default=str))
            return jsonify({
                "metadata": student.get('metadata', {}),
                "result": clean_result
            }), 200
        return jsonify({'error': f'No results found for key "{result_key}".'}), 404
        
    return jsonify({'error': 'No student found with this ID.'}), 404


@app.route('/admin/clear_results', methods=['POST'])
def clear_results():
    if not check_admin_auth(request):
        return jsonify({'error': 'Unauthorized'}), 401
    # Clears all student data and file records
    save_results({'uploaded_files': [], 'student_data': {}})
    return jsonify({'message': 'All results and uploaded file records have been deleted. You can now upload new files.'}), 200

@app.route('/student/download/<string:student_id>/<string:result_key>', methods=['GET'])
def download_marksheet(student_id, result_key):
    all_data = load_results()
    student = all_data['student_data'].get(student_id.upper())

    if not student:
        return jsonify({'error': 'No results found for this Student ID.'}), 404
    
    result = student.get('results', {}).get(result_key)
    
    if not result:
        return jsonify({'error': f'No result found for key "{result_key}".'}), 404

    # Create PDF in memory
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    #college logo - Placeholder
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
    c.drawCentredString(width/2, height - 110, f"OFFICIAL GRADE CARD ({result_key.upper()})")
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width/2, height - 125, "ENGINEERING AND TECHNOLOGY PROGRAM")

    # Student info
    y = height - 150
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Register No: {student.get('metadata', {}).get('studentId', '')}")
    c.drawString(300, y, f"Month & Year: {datetime.now().strftime('%b-%Y')}")
    y -= 15
    c.drawString(50, y, f"Branch: {student.get('metadata', {}).get('branch', '')}")
    c.drawString(300, y, f"Semester: {result.get('semester', '')}")
    y -= 15
    c.drawString(50, y, f"Name of the Candidate: {student.get('metadata', {}).get('name', '')}")

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
    response.headers['Content-Disposition'] = f'attachment; filename={student_id}_{result_key}_marksheet.pdf'
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5000)




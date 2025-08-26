import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
from io import BytesIO, StringIO

# Initialize Flask app
app = Flask(__name__)
# Enable CORS for all routes, allowing the frontend to make requests
CORS(app)

# Define the path for the data file
DATA_FILE = 'students_results.json'

# Admin credentials (for demonstration purposes only - in a real app, use secure hashing)
ADMIN_EMAIL = 'admin@college.com'
ADMIN_PASSWORD = 'adminpassword'

def load_results():
    """Loads student results from the JSON file."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                # Handle empty or invalid JSON file
                return {}
    return {}

def save_results(results):
    """Saves student results to the JSON file."""
    with open(DATA_FILE, 'w') as f:
        json.dump(results, f, indent=4)

# Initialize data file if it doesn't exist
if not os.path.exists(DATA_FILE):
    save_results({})

@app.route('/admin/login', methods=['POST'])
def admin_login():
    """
    Handles admin login.
    Expects JSON payload with 'email' and 'password'.
    Returns a success message or an error if credentials are invalid.
    """
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
        return jsonify({'message': 'Admin login successful!', 'token': 'mock_admin_token'}), 200
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/admin/upload_results', methods=['POST'])
def upload_results():
    """
    Handles uploading student results from Excel (.xlsx) or CSV (.csv) files.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        new_results_data = []

        try:
            if file_extension == 'csv':
                # Read CSV into a pandas DataFrame
                df = pd.read_csv(StringIO(file.read().decode('utf-8')))
            elif file_extension in ['xls', 'xlsx']:
                # Read Excel into a pandas DataFrame
                df = pd.read_excel(BytesIO(file.read()))
            else:
                return jsonify({'error': 'Unsupported file type. Please upload a CSV or Excel file.'}), 400

            # Convert DataFrame to a list of dictionaries (JSON-like format)
            # Ensure column names match expected keys: studentId, name, academicYear, sgpa, cgpa
            # For subjects, you'll need to adapt based on your Excel/CSV structure.
            # Example: assuming subject marks are in columns like 'Math_Marks', 'Physics_Marks'
            # For simplicity, this example expects 'subjects' as a JSON string or assumes specific columns.
            # A more robust solution would require explicit column mapping or a specific structure.

            # Basic conversion, assuming direct column names for simple fields
            # For subjects, if they are in separate columns, you'd need to reconstruct them here.
            # E.g., if you have 'Subject1_Name', 'Subject1_Marks', 'Subject2_Name', 'Subject2_Marks'
            # For now, let's assume 'subjects' is a single column containing a JSON string of subjects,
            # or you'll need to define a clear mapping for subject columns.
            
            # Here's a more flexible approach assuming subject columns are prefixed with 'Subject_'
            temp_results = df.to_dict(orient='records')
            for row in temp_results:
                student_data = {
                    "studentId": str(row.get('studentId', '')).strip(), # Ensure studentId is string
                    "name": row.get('name', ''),
                    "academicYear": row.get('academicYear', ''),
                    "sgpa": row.get('sgpa', 0.0),
                    "cgpa": row.get('cgpa', 0.0),
                    "subjects": []
                }
                # Collect all columns that might be subject-related
                subject_names = [col.replace('_Marks', '') for col in row if '_Marks' in col]
                for s_name in subject_names:
                    marks = row.get(f'{s_name}_Marks')
                    if marks is not None:
                        student_data['subjects'].append({"name": s_name, "marks": marks})
                
                # If 'subjects' column exists and contains a string (e.g., JSON string)
                if 'subjects' in row and isinstance(row['subjects'], str):
                    try:
                        parsed_subjects = json.loads(row['subjects'])
                        if isinstance(parsed_subjects, list):
                            student_data['subjects'].extend(parsed_subjects)
                    except json.JSONDecodeError:
                        pass # Handle malformed JSON string in subjects column
                        
                new_results_data.append(student_data)

            # Filter out entries without a studentId
            new_results_data = [d for d in new_results_data if d.get('studentId')]

        except Exception as e:
            app.logger.error(f"Error processing file: {e}")
            return jsonify({'error': f'Error processing file: {str(e)}. Please ensure the file format is correct and includes "studentId", "name", "academicYear", "sgpa", "cgpa", and subject marks (e.g., "Math_Marks").'}), 400

        if not new_results_data:
            return jsonify({'error': 'No valid student data found in the uploaded file.'}), 400

        all_results = load_results()
        for student_data in new_results_data:
            student_id = student_data.get('studentId')
            if student_id:
                all_results[student_id.upper()] = student_data

        save_results(all_results)
        return jsonify({'message': f'Successfully uploaded {len(new_results_data)} student results from {file.filename}.'}), 200
    return jsonify({'error': 'File upload failed.'}), 500

@app.route('/student/results/<string:student_id>', methods=['GET'])
def get_student_results(student_id):
    """
    Retrieves results for a specific student.
    Takes student_id as a URL parameter.
    Returns student data or a 'not found' message.
    """
    all_results = load_results()
    result = all_results.get(student_id.upper())

    if result:
        return jsonify(result), 200
    return jsonify({'error': 'No results found for this Student ID.'}), 404

if __name__ == '__main__':
    # Run the Flask app on port 5000
    app.run(debug=True, port=5000)

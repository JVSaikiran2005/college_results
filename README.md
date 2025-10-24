# College Results Portal

## 📜 Description

The **College Results Portal** is a lightweight web application designed to manage, display, and facilitate the download of student examination results. It features a public-facing portal where students can look up their results and download official marksheets, and a secure administrative interface for uploading new result data.

---

## ✨ Features

* **Student Result Lookup:** Students can enter their ID to view available semester results.
* **Detailed Marksheet View:** Displays subject-wise Grades, Credits, and Grade Points, along with calculated **SGPA** (Semester Grade Point Average) and **CGPA** (Cumulative Grade Point Average).
* **PDF Marksheet Generation:** Allows students to download their results as a formatted, official PDF document (using ReportLab).
* **Secure Admin Panel:** Allows an administrator to log in and upload new result data via Excel/CSV files, which are then processed and stored in the backend JSON database.

---

## 💻 Technologies Used

### Backend (Python Flask)
* **Python 3.x**
* **Flask** (Web Framework)
* **Pandas** (For reading and processing Excel/CSV files)
* **ReportLab** (For generating dynamic PDF marksheets)
* **Flask-CORS**

### Frontend (Client-side)
* **HTML5**
* **Tailwind CSS** (Utility-first styling)
* **JavaScript (Fetch API)**

---

## 🛠️ Setup and Installation

### Prerequisites

You need **Python 3.x** and **npm** (or yarn) installed on your system.

### 1. Backend Setup

1.  **Clone the repository** (or place the files in a folder).
2.  **Create a Python virtual environment** (recommended):
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Linux/macOS
    .\venv\Scripts\activate  # On Windows
    ```
3.  **Install Python dependencies:**
    ```bash
    pip install Flask flask-cors pandas reportlab
    ```
python -m venv venv
.\venv\Scripts\activate
pip install Flask Flask-Cors
pip install reportlab
pip install pandas openpyxl
python app.py
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -
### 2. Frontend Setup (Optional - for Tailwind development)

If you plan to modify the CSS and need to compile Tailwind, run:

1.  **Install Node dependencies:**
    ```bash
    npm install
    ```

---

## ▶️ How to Run

1.  **Start the Flask server** (ensure your virtual environment is active):
    ```bash
    # Set the Flask application file
    export FLASK_APP=app.py
    # Run the application
    flask run
    ```
    The backend will typically start on `http://127.0.0.1:5000/`.

2.  **Access the Portal:**
    Open the `index.html` file directly in your web browser. The frontend is configured to communicate with the backend on `http://127.0.0.1:5000`.

---

## 🔑 Default Credentials

The admin credentials are hardcoded in `app.py`. **For production, these should be moved to secure environment variables or a database.**

| Role | Email | Password |
| :--- | :--- | :--- |
| **Admin** | `admin@college.com` | `adminpassword` |

You can access the admin login page by clicking the **Admin** button on the top right of the portal.



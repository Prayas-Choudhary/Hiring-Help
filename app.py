# hiring_automation_app.py

import os
import re
import pandas as pd
from openpyxl import Workbook
from docx import Document
from io import BytesIO
import streamlit as st

CANDIDATE_FOLDER = 'resumes'
OUTPUT_FOLDER = 'output'
TRACKER_PATH = os.path.join(OUTPUT_FOLDER, 'excel', 'candidate_tracker.xlsx')
EMAIL_OUTPUT_PATH = os.path.join(OUTPUT_FOLDER, 'emails')

os.makedirs(CANDIDATE_FOLDER, exist_ok=True)
os.makedirs(EMAIL_OUTPUT_PATH, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_FOLDER, 'excel'), exist_ok=True)

# --------- Resume Parsing -----------
def extract_text_from_pdf(file_path):
    try:
        import fitz  # PyMuPDF as an alternative to pdfplumber
    except ImportError:
        raise ImportError("Please install PyMuPDF using 'pip install pymupdf'")

    text = ''
    doc = fitz.open(file_path)
    for page in doc:
        text += page.get_text() + '\n'
    return text

def extract_text_from_docx(file_path):
    doc = Document(file_path)
    return '\n'.join([p.text for p in doc.paragraphs])

def extract_contact_info(text):
    email = re.findall(r'[\w\.-]+@[\w\.-]+', text)
    phone = re.findall(r'\+?\d[\d\s()-]{8,}\d', text)
    return email[0] if email else '', phone[0] if phone else ''

def parse_resume(file_path):
    if file_path.endswith('.pdf'):
        text = extract_text_from_pdf(file_path)
    elif file_path.endswith('.docx'):
        text = extract_text_from_docx(file_path)
    else:
        return None
    email, phone = extract_contact_info(text)
    return {
        'Name': os.path.splitext(os.path.basename(file_path))[0],
        'Email': email,
        'Phone': phone,
        'Summary': text[:300] + '...'
    }

# --------- Tracker Excel File -----------
def update_excel_tracker(candidate_data_list):
    df = pd.DataFrame(candidate_data_list)
    df.to_excel(TRACKER_PATH, index=False)
    print(f"Excel tracker saved to: {TRACKER_PATH}")

# --------- JD Editor and Email Generator -----------
def edit_jd(jd_text):
    lines = jd_text.split('\n')
    clean_lines = [line for line in lines if 'client' not in line.lower() and 'company' not in line.lower()]
    return '\n'.join(clean_lines)

def create_email_draft(candidate_name, jd_text):
    email_template = f"""
Hi {candidate_name},

We found your profile suitable for the following position:

{jd_text}

Please let us know if you're interested.

Regards,
Hiring Team
"""
    with open(os.path.join(EMAIL_OUTPUT_PATH, f"{candidate_name}_email.txt"), 'w') as f:
        f.write(email_template)
    print(f"Email draft saved for {candidate_name}.")

# --------- Main Execution -----------
def main():
    candidate_data_list = []
    for filename in os.listdir(CANDIDATE_FOLDER):
        path = os.path.join(CANDIDATE_FOLDER, filename)
        candidate = parse_resume(path)
        if candidate:
            candidate_data_list.append(candidate)
            jd_text = edit_jd("JD: We are hiring for our client, ABC Corp. Responsibilities include...")
            create_email_draft(candidate['Name'], jd_text)

    update_excel_tracker(candidate_data_list)

    # Streamlit app preview and download
    st.title("Candidate Tracker Preview")
    if candidate_data_list:
        df = pd.DataFrame(candidate_data_list)
        st.dataframe(df)

        buffer = BytesIO()
        df.to_excel(buffer, index=False, engine='openpyxl')
        buffer.seek(0)

        st.download_button(
            label="⬇ Download Excel",
            data=buffer,
            file_name="ranked_candidates.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

if __name__ == '__main__':
    main()

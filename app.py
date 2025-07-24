import os
import re
import fitz
import pandas as pd
from docx import Document
from io import BytesIO
import streamlit as st
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('all-MiniLM-L6-v2')

CANDIDATE_FOLDER = 'resumes'
JD_FOLDER = 'job_descriptions'
OUTPUT_FOLDER = 'output'
EMAIL_OUTPUT_PATH = os.path.join(OUTPUT_FOLDER, 'emails')
TRACKER_PATH = os.path.join(OUTPUT_FOLDER, 'excel', 'candidate_tracker.xlsx')

os.makedirs(CANDIDATE_FOLDER, exist_ok=True)
os.makedirs(JD_FOLDER, exist_ok=True)
os.makedirs(EMAIL_OUTPUT_PATH, exist_ok=True)
os.makedirs(os.path.dirname(TRACKER_PATH), exist_ok=True)

def extract_text_from_pdf(file_path):
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
    phone = re.findall(r'(?<!\d)(\d{10})(?!\d)', text)
    return email[0] if email else '', phone[0] if phone else ''

def extract_skills(text):
    keywords = ['python', 'java', 'sql', 'excel', 'communication', 'machine learning', 'cloud', 'aws', 'azure']
    found = [kw for kw in keywords if kw.lower() in text.lower()]
    return found

def parse_resume(file_path, jd_text):
    if file_path.endswith('.pdf'):
        text = extract_text_from_pdf(file_path)
    elif file_path.endswith('.docx'):
        text = extract_text_from_docx(file_path)
    else:
        return None

    email, phone = extract_contact_info(text)
    name = os.path.splitext(os.path.basename(file_path))[0]
    resume_skills = extract_skills(text)
    jd_skills = extract_skills(jd_text)

    resume_embedding = model.encode(text, convert_to_tensor=True)
    jd_embedding = model.encode(jd_text, convert_to_tensor=True)
    similarity = util.cos_sim(resume_embedding, jd_embedding).item() * 100

    missing_skills = list(set(jd_skills) - set(resume_skills))

    return {
        'Name': name,
        'Email': email,
        'Phone': phone,
        'Match %': round(similarity, 2),
        'Resume Skills': ', '.join(resume_skills),
        'Missing Skills': ', '.join(missing_skills),
        'Summary': text[:300] + '...',
        'Status': 'Pending'
    }

def edit_jd(jd_text):
    clean = []
    for line in jd_text.splitlines():
        if 'client' not in line.lower() and 'company' not in line.lower():
            clean.append(line)
    return '\n'.join(clean)

def create_email_draft(candidate_name, jd_text):
    jd_clean = edit_jd(jd_text)
    body = f"""Hi {candidate_name},

We found your profile suitable for the following opportunity:

{jd_clean}

Please reply if you're interested.

Regards,
Hiring Team"""
    email_path = os.path.join(EMAIL_OUTPUT_PATH, f"{candidate_name}_email.txt")
    with open(email_path, 'w') as f:
        f.write(body)
    return body

def update_excel_tracker(df):
    df.to_excel(TRACKER_PATH, index=False)

def load_text(file):
    if file.name.endswith('.pdf'):
        return extract_text_from_pdf(file)
    elif file.name.endswith('.docx'):
        return extract_text_from_docx(file)
    elif file.name.endswith('.txt'):
        return file.read().decode('utf-8')
    return ''

def main():
    st.title("📄 Smart AI Hiring Assistant")
    st.subheader("Upload Job Description")

    jd_file = st.file_uploader("Upload JD File", type=['pdf', 'docx', 'txt'])
    if jd_file:
        jd_text = load_text(jd_file)
        st.text_area("JD Preview", jd_text, height=200)
        with open(os.path.join(JD_FOLDER, jd_file.name), 'w', encoding='utf-8') as f:
            f.write(jd_text)
    else:
        jd_files = os.listdir(JD_FOLDER)
        if jd_files:
            selected = st.selectbox("Or select existing JD", jd_files)
            with open(os.path.join(JD_FOLDER, selected), 'r', encoding='utf-8') as f:
                jd_text = f.read()
                st.text_area("JD Preview", jd_text, height=200)
        else:
            st.warning("Please upload a Job Description to proceed.")
            return

    st.subheader("📎 Upload Resumes")
    resumes = st.file_uploader("Upload resumes", type=['pdf', 'docx'], accept_multiple_files=True)

    if resumes and jd_text:
        candidates = []
        for file in resumes:
            save_path = os.path.join(CANDIDATE_FOLDER, file.name)
            with open(save_path, 'wb') as f:
                f.write(file.read())
            parsed = parse_resume(save_path, jd_text)
            if parsed:
                candidates.append(parsed)
                create_email_draft(parsed['Name'], jd_text)

        if candidates:
            df = pd.DataFrame(candidates)
            df = df.sort_values(by='Match %', ascending=False).reset_index(drop=True)

            st.success("✅ Matching Completed")
            st.dataframe(df)

            buffer = BytesIO()
            df.to_excel(buffer, index=False, engine='openpyxl')
            buffer.seek(0)

            update_excel_tracker(df)

            st.download_button("⬇ Download Excel", buffer, file_name="ranked_candidates.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == '__main__':
    main()

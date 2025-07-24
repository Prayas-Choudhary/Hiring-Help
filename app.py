import os
import re
import streamlit as st
import pandas as pd
import pdfplumber
from docx import Document
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# -------- Helper Functions --------
def read_text(file):
    if file.name.endswith('.pdf'):
        with pdfplumber.open(file) as pdf:
            return '\n'.join(page.extract_text() for page in pdf.pages if page.extract_text())
    elif file.name.endswith('.docx'):
        doc = Document(file)
        return '\n'.join([para.text for para in doc.paragraphs])
    elif file.name.endswith('.txt'):
        return file.read().decode('utf-8')
    return ""

def extract_info(text):
    name_match = re.findall(r'(?i)(name[:\\s]+)([a-zA-Z\\s]+)', text)
    phone_match = re.findall(r'\\+?\\d[\\d\\s()-]{8,}\\d', text)
    email_match = re.findall(r'[\\w\\.-]+@[\\w\\.-]+', text)
    exp_match = re.findall(r'(?i)(\\d+)[\\s]+(years|yrs)', text)
    ctc_match = re.findall(r'(?i)(CTC|current.*comp).*?(\\d+(?:\\.\\d+)?)(?=\\s|LPA|lpa|\\n)', text)
    ectc_match = re.findall(r'(?i)(ECTC|expected.*comp).*?(\\d+(?:\\.\\d+)?)(?=\\s|LPA|lpa|\\n)', text)
    company_match = re.findall(r'(?i)(company[:\\s]+)([a-zA-Z&\\s]+)', text)
    loc_match = re.findall(r'(?i)(location[:\\s]+)([a-zA-Z,\\s]+)', text)

    return {
        'Name': name_match[0][1].strip() if name_match else '',
        'Phone': phone_match[0] if phone_match else '',
        'Email': email_match[0] if email_match else '',
        'Experience': exp_match[0][0] + " Years" if exp_match else '',
        'CTC': ctc_match[0][1] + " LPA" if ctc_match else '',
        'ECTC': ectc_match[0][1] + " LPA" if ectc_match else '',
        'Current Company': company_match[0][1].strip() if company_match else '',
        'Location': loc_match[0][1].strip() if loc_match else ''
    }

def calculate_similarity(jd_text, resume_text):
    vectorizer = TfidfVectorizer(stop_words='english')
    vectors = vectorizer.fit_transform([jd_text, resume_text])
    score = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
    return round(score * 100, 2)

# -------- Streamlit UI --------
st.title("🧠 AI Hiring Assistant")

# Tab 1: Company Info
with st.sidebar:
    st.header("🔹 Step 1: Enter Company Info")
    company_name = st.text_input("Company Name for Hiring", "")

# Tab 2: Upload JD
st.subheader("📄 Upload Job Description (PDF, DOCX, or TXT)")
jd_file = st.file_uploader("Upload JD", type=["pdf", "docx", "txt"])

# Tab 3: Upload Resumes
st.subheader("📂 Upload Resume(s) to Compare")
resume_files = st.file_uploader("Upload Resumes", type=["pdf", "docx"], accept_multiple_files=True)

if jd_file and resume_files:
    jd_text = read_text(jd_file)
    data = []

    for file in resume_files:
        resume_text = read_text(file)
        info = extract_info(resume_text)
        info['Similarity %'] = calculate_similarity(jd_text, resume_text)
        data.append(info)

    df = pd.DataFrame(data)
    df = df.sort_values(by='Similarity %', ascending=False)

    st.success("✅ Comparison Complete")
    st.dataframe(df)

    # Download Button
    st.download_button("⬇ Download Excel", data=df.to_excel(index=False), file_name="ranked_candidates.xlsx")


import os
import re
import pandas as pd
from docx import Document
from io import BytesIO
import streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def extract_text_from_pdf(file):
    import fitz  # PyMuPDF
    text = ''
    with fitz.open(stream=file.read(), filetype='pdf') as doc:
        for page in doc:
            text += page.get_text()
    return text

def extract_text_from_docx(file):
    doc = Document(file)
    return '\n'.join([p.text for p in doc.paragraphs])

def extract_contact_info(text):
    email = re.findall(r'[\w\.-]+@[\w\.-]+', text)
    phone = re.findall(r'\+?\d[\d\s()-]{8,}\d', text)
    return email[0] if email else '', phone[0] if phone else ''

def extract_text(file):
    if file.name.endswith('.pdf'):
        return extract_text_from_pdf(file)
    elif file.name.endswith('.docx'):
        return extract_text_from_docx(file)
    elif file.name.endswith('.txt'):
        return file.read().decode('utf-8')
    return ''

def compute_similarity(jd_text, resume_text):
    texts = [jd_text, resume_text]
    tfidf = TfidfVectorizer(stop_words='english')
    tfidf_matrix = tfidf.fit_transform(texts)
    sim_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    return round(sim_score * 100, 2)

def parse_resume(file, jd_text):
    text = extract_text(file)
    email, phone = extract_contact_info(text)
    similarity = compute_similarity(jd_text, text)
    return {
        'Name': file.name.replace(".pdf", "").replace(".docx", "").replace(".txt", ""),
        'Email': email,
        'Phone': phone,
        'Similarity %': similarity,
        'Summary': text[:300] + "..."
    }

# Streamlit App
st.title("📄 Automated Hiring Assistant")

tab1, tab2, tab3 = st.tabs(["1️⃣ Company Info", "2️⃣ Upload JD", "3️⃣ Upload Resumes"])

with tab1:
    company_name = st.text_input("Enter Company Name You Are Hiring For")

with tab2:
    jd_file = st.file_uploader("Upload JD File (PDF, DOCX, TXT)", type=['pdf', 'docx', 'txt'])

with tab3:
    resume_files = st.file_uploader("Upload One or More Resumes", type=['pdf', 'docx', 'txt'], accept_multiple_files=True)

if jd_file and resume_files:
    jd_text = extract_text(jd_file)
    results = [parse_resume(file, jd_text) for file in resume_files]
    results.sort(key=lambda x: x['Similarity %'], reverse=True)

    df = pd.DataFrame(results)

    st.subheader("📊 Resume Match Results")
    st.dataframe(df)

    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)

    st.download_button(
        label="⬇ Download Ranked Candidates Excel",
        data=buffer,
        file_name="ranked_candidates.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
s

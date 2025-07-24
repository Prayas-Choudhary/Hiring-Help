import os
import re
import fitz  # PyMuPDF
import pandas as pd
from io import BytesIO
from docx import Document
from sentence_transformers import SentenceTransformer, util
import streamlit as st

# Load model once
model = SentenceTransformer('all-MiniLM-L6-v2')

# Utility: Extract text
def extract_text_from_pdf(file):
    text = ''
    pdf = fitz.open(stream=file.read(), filetype="pdf")
    for page in pdf:
        text += page.get_text()
    return text

def extract_text_from_docx(file):
    doc = Document(file)
    return '\n'.join([p.text for p in doc.paragraphs])

def extract_text(file):
    name = file.name.lower()
    if name.endswith('.pdf'):
        return extract_text_from_pdf(file)
    elif name.endswith('.docx'):
        return extract_text_from_docx(file)
    elif name.endswith('.txt'):
        return file.read().decode('utf-8')
    else:
        return ''

# Utility: Extract contact info
def extract_contact_info(text):
    email_match = re.findall(r'[\w\.-]+@[\w\.-]+', text)
    phone_match = re.findall(r'\+?\d[\d\s\-().]{8,}\d', text)
    email = email_match[0] if email_match else ''
    phone = phone_match[0] if phone_match else ''
    return email, phone

# Utility: Resume Parser
def parse_resume(file, jd_embedding):
    resume_text = extract_text(file)
    email, phone = extract_contact_info(resume_text)
    name = os.path.splitext(file.name)[0]

    # Embedding and similarity
    resume_embedding = model.encode(resume_text, convert_to_tensor=True)
    similarity = util.cos_sim(resume_embedding, jd_embedding)[0][0].item() * 100

    return {
        'Name': name,
        'Email': email,
        'Phone': phone,
        'Similarity %': round(similarity, 2),
        'Summary': resume_text[:500] + '...' if len(resume_text) > 500 else resume_text
    }

# App UI
st.set_page_config(page_title="Smart AI Hiring Assistant", layout="wide")
st.title("📄 Smart AI Hiring Assistant")

col1, col2 = st.columns(2)
with col1:
    company_name = st.text_input("🏢 Enter Company Name", "")

with col2:
    jd_file = st.file_uploader("📑 Upload Job Description (PDF, DOCX, TXT)", type=['pdf', 'docx', 'txt'])

resume_files = st.file_uploader("📁 Upload Resume(s)", type=['pdf', 'docx'], accept_multiple_files=True)

if jd_file and resume_files:
    jd_text = extract_text(jd_file)
    jd_embedding = model.encode(jd_text, convert_to_tensor=True)

    candidate_data = []
    for file in resume_files:
        try:
            parsed = parse_resume(file, jd_embedding)
            candidate_data.append(parsed)
        except Exception as e:
            st.error(f"❌ Error reading {file.name}: {e}")

    if candidate_data:
        df = pd.DataFrame(candidate_data).sort_values(by='Similarity %', ascending=False)

        st.subheader("📊 Candidate Matching Results")
        st.dataframe(df, use_container_width=True)

        buffer = BytesIO()
        df.to_excel(buffer, index=False, engine='openpyxl')
        buffer.seek(0)

        st.download_button(
            label="⬇ Download Excel",
            data=buffer,
            file_name=f"{company_name}_candidates.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

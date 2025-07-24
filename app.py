import os
import re
import pandas as pd
import fitz  # pymupdf
from io import BytesIO
from docx import Document
import streamlit as st
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('all-MiniLM-L6-v2')

st.set_page_config(page_title="JD-Resume Matcher", layout="wide")

def extract_text_from_pdf(file):
    text = ""
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
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

def get_similarity(jd_text, resume_text):
    jd_embedding = model.encode(jd_text, convert_to_tensor=True)
    resume_embedding = model.encode(resume_text, convert_to_tensor=True)
    similarity = util.pytorch_cos_sim(jd_embedding, resume_embedding).item()
    return round(similarity * 100, 2)

def parse_resume(file, jd_text):
    filename = file.name
    ext = filename.lower().split('.')[-1]
    if ext == "pdf":
        resume_text = extract_text_from_pdf(file)
    elif ext == "docx":
        resume_text = extract_text_from_docx(file)
    else:
        return None

    email, phone = extract_contact_info(resume_text)
    similarity = get_similarity(jd_text, resume_text)

    return {
        'Name': os.path.splitext(filename)[0],
        'Email': email,
        'Phone': phone,
        'Similarity %': similarity,
        'Summary': resume_text[:300].strip().replace('\n', ' ') + '...'
    }

def extract_text_from_uploaded_jd(jd_file):
    ext = jd_file.name.lower().split('.')[-1]
    if ext == "pdf":
        return extract_text_from_pdf(jd_file)
    elif ext == "docx":
        return extract_text_from_docx(jd_file)
    elif ext == "txt":
        return jd_file.read().decode("utf-8")
    else:
        st.error("Unsupported JD file format")
        return ""

def main():
    st.title("💼 JD–Resume Matching App")

    with st.sidebar:
        st.header("📌 Instructions")
        st.markdown("""
        1. Fill the company name  
        2. Upload JD file (PDF/DOCX/TXT)  
        3. Upload 1 or more resumes (PDF/DOCX)  
        4. View preview and download ranked Excel  
        """)

    company_name = st.text_input("🧩 Enter Company Name")

    st.subheader("📄 Upload Job Description (PDF/DOCX/TXT)")
    jd_file = st.file_uploader("Upload JD File", type=["pdf", "docx", "txt"])

    st.subheader("📁 Upload Candidate Resumes")
    resume_files = st.file_uploader("Upload Resume Files", type=["pdf", "docx"], accept_multiple_files=True)

    if jd_file and resume_files:
        jd_text = extract_text_from_uploaded_jd(jd_file)
        results = []
        for resume_file in resume_files:
            parsed = parse_resume(resume_file, jd_text)
            if parsed:
                results.append(parsed)

        if results:
            df = pd.DataFrame(results)
            df.sort_values("Similarity %", ascending=False, inplace=True)

            st.success(f"✅ {len(results)} resumes analyzed and ranked by similarity to JD.")
            st.dataframe(df)

            buffer = BytesIO()
            df.to_excel(buffer, index=False, engine='openpyxl')
            buffer.seek(0)

            st.download_button(
                label="⬇ Download Ranked Excel",
                data=buffer,
                file_name=f"{company_name}_ranked_candidates.xlsx" if company_name else "ranked_candidates.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("No valid resumes could be parsed.")
    else:
        st.info("Please upload JD and resumes to begin.")

if __name__ == "__main__":
    main()

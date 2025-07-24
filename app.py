import streamlit as st
import os
import docx2txt
import pdfplumber
import base64
import spacy
import re
import pandas as pd
from io import BytesIO
from sentence_transformers import SentenceTransformer, util

# Load NLP & Semantic Model
nlp = spacy.load("en_core_web_sm")
model = SentenceTransformer('all-MiniLM-L6-v2')

# ------------ Resume Parsing Utilities ------------

def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

def extract_text_from_docx(file):
    return docx2txt.process(file)

def extract_resume_text(file):
    if file.type == "application/pdf":
        return extract_text_from_pdf(file)
    elif file.type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
        return extract_text_from_docx(file)
    else:
        return ""

def extract_email(text):
    match = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    return match[0] if match else ""

def extract_phone(text):
    match = re.findall(r'(\+91[\-\s]?)?[6789]\d{9}', text)
    return match[0] if match else ""

def extract_name(text):
    lines = text.strip().split('\n')
    for line in lines:
        doc = nlp(line.strip())
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                return ent.text
    return ""

def extract_experience(text):
    match = re.findall(r'([0-9]+(?:\.[0-9]+)?)\s*(?:years|yrs|yr)', text.lower())
    return f"{match[0]} years" if match else "Not Found"

def extract_location(text):
    for line in text.split('\n'):
        if 'location' in line.lower():
            return line.split(':')[-1].strip()
    return "Not Found"

def extract_current_company(text):
    for line in text.split('\n'):
        if any(keyword in line.lower() for keyword in ['current company', 'working at', 'employed at']):
            return line.split(':')[-1].strip()
    return "Not Found"

def extract_resume_details(text):
    return {
        "Name": extract_name(text),
        "Experience": extract_experience(text),
        "Location": extract_location(text),
        "Current Company": extract_current_company(text),
        "Email": extract_email(text),
        "Phone": extract_phone(text)
    }

# ------------ JD-Resume Similarity ------------

def calculate_similarity(jd_text, resume_text):
    jd_emb = model.encode(jd_text, convert_to_tensor=True)
    resume_emb = model.encode(resume_text, convert_to_tensor=True)
    similarity = util.cos_sim(jd_emb, resume_emb)
    return round(float(similarity[0][0]) * 100, 2)

# ------------ UI Starts ------------

st.set_page_config(layout="wide", page_title="Smart AI Hiring Assistant")

st.title("📄 Smart AI Hiring Assistant")

with st.sidebar:
    st.header("📢 Hiring Info")
    company_name = st.text_input("Company / Client Name", "")

st.markdown("### Step 1: Upload JD (PDF/DOCX/TXT)")
jd_file = st.file_uploader("Upload JD File", type=["pdf", "docx", "txt"], key="jd")

st.markdown("### Step 2: Upload Resume(s) (PDF/DOCX)")
resume_files = st.file_uploader("Upload Resume Files", type=["pdf", "docx"], accept_multiple_files=True, key="resumes")

results = []

if jd_file and resume_files:
    with st.spinner("🔍 Analyzing..."):
        # Load JD Text
        if jd_file.type == "application/pdf":
            jd_text = extract_text_from_pdf(jd_file)
        elif jd_file.type == "text/plain":
            jd_text = jd_file.read().decode()
        else:
            jd_text = extract_text_from_docx(jd_file)

        for resume in resume_files:
            resume_text = extract_resume_text(resume)
            if not resume_text.strip():
                continue

            details = extract_resume_details(resume_text)
            similarity = calculate_similarity(jd_text, resume_text)

            results.append({
                "File": resume.name,
                "Name": details["Name"],
                "Experience": details["Experience"],
                "Location": details["Location"],
                "Current Company": details["Current Company"],
                "Email": details["Email"],
                "Phone": details["Phone"],
                "Similarity (%)": similarity
            })

    # Sort by similarity
    df = pd.DataFrame(results)
    df = df.sort_values(by="Similarity (%)", ascending=False)

    st.success("✅ Analysis Complete!")

    st.markdown("### 📊 Ranked Candidate Table")
    st.dataframe(df.reset_index(drop=True), use_container_width=True)

    # Download as Excel
    output = BytesIO()
    df.to_excel(output, index=False)
    st.download_button(
        label="⬇ Download Excel Report",
        data=output.getvalue(),
        file_name="AI_Ranked_Candidates.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("ℹ Please upload both JD and at least one Resume to continue.")

import os
import re
import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from docx import Document
from io import BytesIO
from sentence_transformers import SentenceTransformer, util

# ✅ Force model to load on CPU to avoid Streamlit cloud errors
model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')

def extract_text_from_pdf(file):
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)

def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_text_from_txt(file):
    return file.read().decode("utf-8")

def extract_text(file):
    filename = file.name.lower()
    if filename.endswith(".pdf"):
        return extract_text_from_pdf(file)
    elif filename.endswith(".docx"):
        return extract_text_from_docx(file)
    elif filename.endswith(".txt"):
        return extract_text_from_txt(file)
    else:
        return ""

def compute_similarity(jd_text, resume_text):
    jd_emb = model.encode(jd_text, convert_to_tensor=True)
    resume_emb = model.encode(resume_text, convert_to_tensor=True)
    score = util.cos_sim(jd_emb, resume_emb).item()
    return round(score * 100, 2)

def extract_candidate_details(text):
    clean_text = re.sub(r'\s+', ' ', text)
    
    # 🌟 Improved Name Detection
    name = ""
    name_match = re.search(r"Name\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", clean_text)
    if name_match:
        name = name_match.group(1)
    else:
        # Fallback 1: Top-most lines with 2+ capitalized words
        lines = text.splitlines()
        for line in lines[:5]:
            probable = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", line)
            if probable:
                name = probable[0]
                break
        # Fallback 2: First bold or all-uppercase large word-like chunks (if HTML/parsing available — skipped here)

    email = ""
    phone = ""
    experience = ""
    location = ""
    current_company = ""
    ctc = ""
    ectc = ""

    email_match = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    if email_match:
        email = email_match[0]

    phone_match = re.findall(r"(?:\+91[-\s]?|0)?[6-9]\d{9}", text)
    if phone_match:
        phone = phone_match[0]

    exp_match = re.findall(r"(\d+\.?\d*)\s+(?:years?|yrs?)\s+of\s+experience", text, re.I)
    if exp_match:
        experience = exp_match[0]

    location_match = re.findall(r"Location[:\- ]*(.*)", text, re.I)
    if location_match:
        location = location_match[0].strip().split("\n")[0]

    company_match = re.findall(r"(?:Currently\s+at|Working\s+at|Employer[:\- ]*)(.*)", text, re.I)
    if company_match:
        current_company = company_match[0].strip().split("\n")[0]

    ctc_match = re.findall(r"CTC[:\- ]*₹?(\d+[.,]?\d*)", text, re.I)
    if ctc_match:
        ctc = ctc_match[0]

    ectc_match = re.findall(r"(?:Expected\s*CTC|ECTC)[:\- ]*₹?(\d+[.,]?\d*)", text, re.I)
    if ectc_match:
        ectc = ectc_match[0]

    return {
        "Name": name,
        "Email": email,
        "Mobile": phone,
        "Experience": experience,
        "Location": location,
        "Current Company": current_company,
        "CTC": ctc,
        "ECTC": ectc
    }

def main():
    st.set_page_config(layout="wide")
    st.title("📄 Smart AI Hiring Assistant")

    st.markdown("### Step 1: Enter Company Name")
    company_name = st.text_input("Company you're hiring for", placeholder="E.g., TCS, Accenture, etc.")

    st.markdown("### Step 2: Upload Job Description (JD)")
    jd_file = st.file_uploader("Upload JD File", type=["pdf", "docx", "txt"])

    st.markdown("### Step 3: Upload Candidate Resumes")
    resumes = st.file_uploader("Upload One or More Resumes", type=["pdf", "docx", "txt"], accept_multiple_files=True)

    if jd_file and resumes:
        jd_text = extract_text(jd_file)
        data = []

        for resume_file in resumes:
            try:
                resume_text = extract_text(resume_file)
                similarity = compute_similarity(jd_text, resume_text)
                details = extract_candidate_details(resume_text)
                details["Similarity %"] = similarity
                data.append(details)
            except Exception as e:
                st.warning(f"❌ Could not process {resume_file.name}: {e}")

        if data:
            df = pd.DataFrame(data)
            df = df.sort_values(by="Similarity %", ascending=False)

            st.markdown("### 📊 Candidate Ranking")
            st.dataframe(df, use_container_width=True)

            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)

            st.download_button(
                "⬇ Download Excel",
                data=excel_buffer,
                file_name="ranked_candidates.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

if __name__ == "__main__":
    main()

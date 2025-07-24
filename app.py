import os
import re
import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from docx import Document
from io import BytesIO
from fpdf import FPDF
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('all-MiniLM-L6-v2')

# ========== File Extractors ==========

def extract_text_from_pdf(file):
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)

def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_text_from_txt(file):
    return file.read().decode("utf-8", errors="ignore")

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

# ========== Similarity Scoring ==========

def compute_similarity(jd_text, resume_text):
    jd_emb = model.encode(jd_text, convert_to_tensor=True)
    resume_emb = model.encode(resume_text, convert_to_tensor=True)
    score = util.cos_sim(jd_emb, resume_emb).item()
    return round(score * 100, 2)

# ========== Candidate Detail Extractor ==========

def extract_candidate_name(text):
    # Clean and limit to top part of resume
    top_text = text[:1000].replace('\n', ' ').replace('\r', '').strip()

    # 1. Direct label match: Name: John Doe
    name_match = re.search(r"\bName\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", top_text)
    if name_match:
        return name_match.group(1)

    # 2. Try to find first few capitalized words near top that don't match keywords
    lines = text.strip().split('\n')[:20]  # Only top part of resume
    lines = [line.strip() for line in lines if line.strip()]
    skip_keywords = ['Resume', 'Curriculum Vitae', 'CV', 'Profile', 'Email', 'Phone', 'Contact', 'Mobile']
    potential_names = []

    for line in lines:
        if any(word.lower() in line.lower() for word in skip_keywords):
            continue
        # Match 2-3 capitalized words (common for names)
        match = re.match(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})$", line.strip())
        if match:
            potential_names.append(match.group(1))

    if potential_names:
        return potential_names[0]

    # 3. Backup fallback: match first multi-capitalized word sequence in top text
    match = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", top_text)
    if match:
        return match.group(1)

    return ""


    # Email and phone
    email = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", clean_text)
    phone = re.search(r"(?:\+91[-\s]?|0)?[6-9]\d{9}", clean_text)

    # Experience
    experience = ""
    exp_match = re.search(r"(?:\bExp(?:erience)?\b\s*[:\-]?\s*)(\d+\.?\d*)\s*(?:years|yrs)?", clean_text, re.I)
    if not exp_match:
        exp_match = re.search(r"(\d+\.?\d*)\s*(?:years|yrs)\s+of\s+experience", clean_text, re.I)
    if exp_match:
        experience = exp_match.group(1)

    # Location
    location_match = re.search(r"\bLocation\s*[:\-]?\s*([A-Za-z ,]+)", clean_text, re.I)
    location = location_match.group(1).strip() if location_match else ""

    # Current company
    company = ""
    company_match = re.search(r"(?:Currently working at|Current Company|Company Name)\s*[:\-]?\s*(.+?)(?:\n|\.|,|$)", text, re.I)
    if company_match:
        company = company_match.group(1).strip()

    # CTC and ECTC
    ctc = ""
    ectc = ""
    ctc_match = re.search(r"\bCTC\s*[:\-]?\s*₹?(\d+[.,]?\d*)", clean_text, re.I)
    ectc_match = re.search(r"\b(?:Expected|ECTC)\s*[:\-]?\s*₹?(\d+[.,]?\d*)", clean_text, re.I)
    if ctc_match:
        ctc = ctc_match.group(1)
    if ectc_match:
        ectc = ectc_match.group(1)

    return {
        "Name": name,
        "Email": email.group(0) if email else "",
        "Mobile": phone.group(0) if phone else "",
        "Experience": experience,
        "Location": location,
        "Current Company": company,
        "CTC": ctc,
        "ECTC": ectc
    }

# ========== Streamlit App ==========

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
            resume_text = extract_text(resume_file)
            similarity = compute_similarity(jd_text, resume_text)
            details = extract_candidate_details(resume_text)
            details["Similarity %"] = similarity
            data.append(details)

        df = pd.DataFrame(data)
        df = df.sort_values(by="Similarity %", ascending=False)

        st.markdown("### 📊 Ranked Candidates")
        st.dataframe(df, use_container_width=True)

        # Excel Export
        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)

        st.download_button(
            "⬇ Download Excel Report",
            data=excel_buffer,
            file_name="ranked_candidates.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

if __name__ == "__main__":
    main()

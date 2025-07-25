import os
import re
import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from docx import Document
from io import BytesIO
from fpdf import FPDF
from sentence_transformers import SentenceTransformer, util

from functools import lru_cache

@lru_cache(maxsize=1)
def load_model():
    return SentenceTransformer('all-MiniLM-L6-v2')

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
    jd_emb = load_model().encode(jd_text, convert_to_tensor=True)
    resume_emb = load_model().encode(resume_text, convert_to_tensor=True)
    score = util.cos_sim(jd_emb, resume_emb).item()
    return round(score * 100, 2)

def generate_remark(similarity, experience, skills_matched=None):
    if similarity >= 75:
        return "Highly suitable – strong JD match."
    elif similarity >= 50:
        return "Moderately suitable – partial match."
    else:
        return "Less suitable – consider alternate role."

def extract_name(text, filename="Unknown"):
    # Try from resume content
    name = ""
    lines = text.strip().split("\n")[:20]  # Only look at top
    for line in lines:
        if re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+$', line.strip()):
            name = line.strip().title()
            break

    # Fallback to filename (Naukri_JohnDoe5yrs.pdf → John Doe)
    if not name:
        name_from_file = os.path.splitext(os.path.basename(filename))[0]
        parts = re.findall(r'[A-Za-z]+', name_from_file)
        if len(parts) >= 2:
            name = f"{parts[0]} {parts[1]}"
        else:
            name = "Unknown"

    return name.title()

def extract_candidate_details(text, filename="Unknown"):
    clean_text = text.replace("\n", " ").replace("\r", " ")

    name = extract_name(text, filename)

    email = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", clean_text)
    phone = re.search(r"(?:\+91[-\s]?|0)?[6-9]\d{9}", clean_text)

    experience = ""
    exp_match = re.search(r"(\d+(?:\.\d+)?)\s+(?:years?|yrs?)\s+of\s+experience", clean_text, re.I)
    if exp_match:
        experience = exp_match.group(1)

    location = ""
    loc_match = re.search(r"Location[:\-]?\s*(\w+[\w\s,]*)", clean_text, re.I)
    if loc_match:
        location = loc_match.group(1).strip()

    current_company = ""
    company_patterns = [
        r"Currently\s+(?:working|employed)\s+at\s*[:\-]?\s*([A-Za-z0-9 &,.]+)",
        r"Working\s+at\s*[:\-]?\s*([A-Za-z0-9 &,.]+)",
        r"Presently\s+working\s+at\s*[:\-]?\s*([A-Za-z0-9 &,.]+)",
        r"Company\s*[:\-]?\s*([A-Za-z0-9 &,.]+)"
    ]
    for pattern in company_patterns:
        match = re.search(pattern, clean_text, re.I)
        if match:
            current_company = match.group(1).strip()
            break

    ctc = ""
    ctc_match = re.search(r"CTC\s*[:\-]?\s*₹?([\d.,]+)", clean_text, re.I)
    if ctc_match:
        ctc = ctc_match.group(1)

    ectc = ""
    ectc_match = re.search(r"(?:Expected|ECTC)\s*[:\-]?\s*₹?([\d.,]+)", clean_text, re.I)
    if ectc_match:
        ectc = ectc_match.group(1)

    return {
        "Name": name,
        "Email": email.group() if email else "",
        "Mobile": phone.group() if phone else "",
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
            resume_text = extract_text(resume_file)
            similarity = compute_similarity(jd_text, resume_text)
            details = extract_candidate_details(resume_text, resume_file.name)
            details = {
                "Name": details["Name"],
                "Similarity %": similarity,
                "Email": details["Email"],
                "Mobile": details["Mobile"],
                "Experience": details["Experience"],
                "Location": details["Location"],
                "Current Company": details["Current Company"],
                "CTC": details["CTC"],
                "ECTC": details["ECTC"],
                "Remarks": generate_remark(similarity, details["Experience"])
            }
            data.append(details)

        df = pd.DataFrame(data)
        df = df.sort_values(by="Similarity %", ascending=False)

        st.markdown("### 📊 Candidate Ranking")
        st.dataframe(df, use_container_width=True)

        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)

        st.download_button("⬇ Download Excel", data=excel_buffer, file_name="ranked_candidates.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == "__main__":
    main()

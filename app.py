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

def extract_candidate_details(text, jd_text=""):
    clean_text = text.strip().replace('\n', ' ')
    name = ""
    name_match = re.search(r"Name\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", clean_text)
    if name_match:
        name = name_match.group(1)
    else:
        name_match = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", clean_text)
        if name_match:
            name = name_match[0]

    email_match = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", clean_text)
    phone_match = re.findall(r"(?:\+91[-\s]?|0)?[6-9]\d{9}", clean_text)

    email = email_match[0] if email_match else ""
    phone = phone_match[0] if phone_match else ""

    # Experience
    experience = ""
    exp_match = re.findall(r"(\d+\.?\d*)\s+(?:years?|yrs?)\s+of\s+experience", clean_text, re.I)
    if exp_match:
        experience = exp_match[0]

    # Location
    location_match = re.findall(r"Location[:\- ]*(.*)", clean_text, re.I)
    location = location_match[0].strip() if location_match else ""

    # Improved Current Company Extraction
    current_company = ""
    company_patterns = [
        r"(?:currently\s+(?:working|employed)\s+(?:at|with)\s*)([A-Z][\w&.,\- ]+)",
        r"(?:working\s+(?:at|with)\s*)([A-Z][\w&.,\- ]+)",
        r"(?:presently\s+(?:associated|working)\s+(?:with|at)\s*)([A-Z][\w&.,\- ]+)",
        r"(?:employer\s*[:\- ]*)([A-Z][\w&.,\- ]+)",
        r"(?:experience\s*[:\- ]*)([A-Z][\w&.,\- ]+)",
        r"(?:professional\s+experience.*?)\b([A-Z][\w&.,\- ]+)\b.*?(?:present|current|till date)",
    ]
    for pattern in company_patterns:
        match = re.search(pattern, clean_text, re.I | re.DOTALL)
        if match:
            current_company = match.group(1).strip()
            break

    # Fallback: check top 10 lines
    if not current_company:
        lines = text.split("\n")[:10]
        for line in lines:
            if "Pvt" in line or "Ltd" in line or "Technologies" in line or "Inc" in line or "Solutions" in line:
                current_company = line.strip()
                break

    # CTC & ECTC
    ctc_match = re.findall(r"CTC[:\- ]*₹?(\d+[.,]?\d*)", clean_text, re.I)
    ectc_match = re.findall(r"(?:Expected|ECTC)[:\- ]*₹?(\d+[.,]?\d*)", clean_text, re.I)
    ctc = ctc_match[0] if ctc_match else ""
    ectc = ectc_match[0] if ectc_match else ""

    # Generate simple remarks
    remarks = ""
    exp = float(experience) if experience else 0
    if jd_text:
        jd_text_lower = jd_text.lower()
        matched_keywords = 0
        for keyword in ["python", "excel", "sql", "communication", "machine learning", "sales", "accounting", "data", "project"]:
            if keyword in jd_text_lower and keyword in clean_text.lower():
                matched_keywords += 1

        if exp >= 3 and matched_keywords >= 3:
            remarks = f"Candidate has {exp} years of experience and matches core skills. Likely a good fit."
        elif exp >= 1 and matched_keywords >= 2:
            remarks = f"Some relevant experience with partial skill match. May need further evaluation."
        else:
            remarks = f"Limited experience or low skill match. Possibly not suitable."
    else:
        remarks = "Job description not provided to evaluate suitability."

    return {
        "Name": name,
        "Email": email,
        "Mobile": phone,
        "Experience": experience,
        "Location": location,
        "Current Company": current_company,
        "CTC": ctc,
        "ECTC": ectc,
        "Remarks": remarks
    }


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

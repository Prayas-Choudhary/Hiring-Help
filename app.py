import streamlit as st
import os
import docx2txt
import pdfplumber
import pandas as pd
import re
from difflib import SequenceMatcher
from io import BytesIO
from pathlib import Path

st.set_page_config(page_title="Smart AI Hiring Assistant", layout="wide")

st.title("🤖 Smart AI Hiring Assistant")

company_name = st.text_input("🏢 Enter the Company Name for which you're hiring:")

st.markdown("### 📄 Upload Job Description (JD)")
jd_file = st.file_uploader("Upload Job Description", type=["pdf", "docx", "txt"], key="jd")

st.markdown("### 📂 Upload Resume(s)")
resume_files = st.file_uploader("Upload Resume(s)", accept_multiple_files=True, type=["pdf", "docx", "txt"], key="resumes")

# ---------- Helper Functions ------------

def extract_text(file):
    text = ""
    if file.name.endswith(".pdf"):
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    elif file.name.endswith(".docx"):
        text = docx2txt.process(file)
    elif file.name.endswith(".txt"):
        text = str(file.read(), "utf-8")
    return text.strip()

def similar(a, b):
    return round(SequenceMatcher(None, a, b).ratio() * 100, 2)

def extract_name(text, filename=""):
    name = ""
    clean_text = re.sub(r"\s+", " ", text)
    name_match = re.search(r"Name\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", clean_text)
    if name_match:
        name = name_match.group(1)
    else:
        found_names = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", clean_text)
        if found_names:
            name = found_names[0]
        else:
            # Try extracting from filename
            base = Path(filename).stem
            parts = base.replace("Naukri_", "").split("_")
            for p in parts:
                if p.isalpha():
                    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', p)
                    break
    return name.strip().title()

def extract_email(text):
    match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    return match.group(0) if match else ""

def extract_phone(text):
    match = re.search(r"\b(?:\+91[-\s]?|0)?[6-9]\d{9}\b", text)
    return match.group(0) if match else ""

def extract_location(text):
    loc_keywords = ['Location', 'Based in', 'City', 'Current Location', 'Residing at']
    for keyword in loc_keywords:
        match = re.search(fr"{keyword}\s*[:\-]?\s*([A-Za-z\s]+)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip().title()
    return ""

def extract_ctc(text):
    match = re.search(r"(CTC|Current CTC)\s*[:\-]?\s*₹?\s*([\d.,]+[ ]?(LPA|lacs|Lakhs)?)", text)
    return match.group(2).strip() if match else ""

def extract_ectc(text):
    match = re.search(r"(Expected CTC|ECTC)\s*[:\-]?\s*₹?\s*([\d.,]+[ ]?(LPA|lacs|Lakhs)?)", text)
    return match.group(2).strip() if match else ""

def convert_df_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Candidates")
        workbook = writer.book
        worksheet = writer.sheets["Candidates"]
        for i, col in enumerate(df.columns):
            worksheet.set_column(i, i, 20)
    output.seek(0)
    return output

# ---------- Processing ------------

if jd_file and resume_files:
    jd_text = extract_text(jd_file)

    results = []
    for file in resume_files:
        resume_text = extract_text(file)
        similarity = similar(jd_text, resume_text)
        name = extract_name(resume_text, file.name)
        email = extract_email(resume_text)
        phone = extract_phone(resume_text)
        location = extract_location(resume_text)
        ctc = extract_ctc(resume_text)
        ectc = extract_ectc(resume_text)

        results.append({
            "Sr. No.": len(results)+1,
            "Name": name,
            "Similarity (%)": similarity,
            "Email": email,
            "Mobile": phone,
            "Location": location,
            "CTC": ctc,
            "ECTC": ectc,
            "Resume Filename": file.name
        })

    df = pd.DataFrame(results)
    df = df.sort_values(by="Similarity (%)", ascending=False)

    st.markdown("### 📊 Candidate Ranking")
    st.dataframe(df, use_container_width=True)

    excel_data = convert_df_to_excel(df)
    st.download_button("📥 Download Candidate Sheet", data=excel_data, file_name="Smart_AI_Hiring_Candidates.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

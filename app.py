import streamlit as st
import os
import docx2txt
import pdfplumber
import pandas as pd
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from io import BytesIO
from pathlib import Path
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

nltk.download('punkt')
nltk.download('stopwords')

st.set_page_config(page_title="Smart AI Hiring Assistant", layout="wide")
st.title("🤖 Smart AI Hiring Assistant")

company_name = st.text_input("🏢 Enter the Company Name for which you're hiring:")
jd_file = st.file_uploader("📄 Upload Job Description", type=["pdf", "docx", "txt"], key="jd")
resume_files = st.file_uploader("📂 Upload Resume(s)", type=["pdf", "docx", "txt"], accept_multiple_files=True, key="resumes")

# ---------- Helper Functions ------------

def extract_text(file):
    text = ""
    if file.name.endswith(".pdf"):
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    elif file.name.endswith(".docx"):
        text = docx2txt.process(file)
    elif file.name.endswith(".txt"):
        text = file.read().decode("utf-8")
    return text.strip()

def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = word_tokenize(text)
    stop_words = set(stopwords.words("english"))
    filtered = [w for w in tokens if w not in stop_words]
    return " ".join(filtered)

def tfidf_similarity(text1, text2):
    vect = TfidfVectorizer()
    tfidf_matrix = vect.fit_transform([text1, text2])
    return round(cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0] * 100, 2)

def jaccard_similarity(text1, text2):
    set1 = set(text1.split())
    set2 = set(text2.split())
    if not set1 or not set2:
        return 0.0
    return round(len(set1 & set2) / len(set1 | set2) * 100, 2)

def keyword_overlap_score(jd_keywords, resume_text):
    resume_tokens = set(resume_text.split())
    match_count = sum(1 for kw in jd_keywords if kw in resume_tokens)
    return round((match_count / len(jd_keywords)) * 100, 2) if jd_keywords else 0

def compute_combined_score(jd_text, resume_text):
    clean_jd = clean_text(jd_text)
    clean_resume = clean_text(resume_text)
    tfidf_score = tfidf_similarity(clean_jd, clean_resume)
    jaccard_score = jaccard_similarity(clean_jd, clean_resume)
    jd_keywords = clean_jd.split()
    keyword_score = keyword_overlap_score(jd_keywords, clean_resume)
    combined = (0.5 * tfidf_score) + (0.3 * jaccard_score) + (0.2 * keyword_score)
    return round(combined, 2)

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
        worksheet = writer.sheets["Candidates"]
        for i, col in enumerate(df.columns):
            worksheet.set_column(i, i, 22)
    output.seek(0)
    return output

# ---------- Main App Logic ------------

if jd_file and resume_files:
    jd_text = extract_text(jd_file)
    results = []

    for file in resume_files:
        resume_text = extract_text(file)
        score = compute_combined_score(jd_text, resume_text)
        name = extract_name(resume_text, file.name)
        email = extract_email(resume_text)
        phone = extract_phone(resume_text)
        location = extract_location(resume_text)
        ctc = extract_ctc(resume_text)
        ectc = extract_ectc(resume_text)

        results.append({
            "Sr. No.": len(results)+1,
            "Name": name,
            "Similarity (%)": score,
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

import streamlit as st
import os
import pdfplumber
import docx2txt
import base64
import re
import pandas as pd
import tempfile
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher
from collections import Counter
import string

# ------------------- File Text Extraction -------------------

def extract_text_from_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        return "\n".join([page.extract_text() or '' for page in pdf.pages])

def extract_text_from_docx(docx_file):
    return docx2txt.process(docx_file)

def extract_text(file):
    if file.name.endswith('.pdf'):
        return extract_text_from_pdf(file)
    elif file.name.endswith('.docx'):
        return extract_text_from_docx(file)
    elif file.name.endswith('.txt'):
        return file.read().decode('utf-8')
    else:
        return ''

# ------------------- Cleaning & Tokenizing -------------------

def clean_text(text):
    text = text.lower()
    text = re.sub(r'[\r\n]+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def tokenize(text):
    return clean_text(text).split()

# ------------------- Resume Field Extractors -------------------

def extract_email(text):
    match = re.search(r'\b[\w.-]+?@\w+?\.\w+?\b', text)
    return match.group(0) if match else ''

def extract_phone(text):
    match = re.search(r'\b(\+91[\s\-]?)?[6789]\d{9}\b', text)
    return match.group(0) if match else ''

def extract_name_from_filename(filename):
    base = os.path.basename(filename)
    name = os.path.splitext(base)[0]
    if 'naukri_' in name.lower():
        parts = name.split('_')
        if len(parts) >= 2:
            return parts[1].title()
    return name.title()

def extract_experience(text):
    matches = re.findall(r'(\d{4})\s*[-–to]{1,3}\s*(\d{4}|present)', text, re.IGNORECASE)
    years = []
    for start, end in matches:
        try:
            start, end = int(start), 2025 if 'present' in end.lower() else int(end)
            if 1900 < start <= end:
                years.append(end - start)
        except:
            continue
    return f"{sum(years)} years" if years else ''

def extract_location(text):
    locations = re.findall(r'\b(?:Mumbai|Delhi|Bangalore|Hyderabad|Pune|Chennai|Noida|Gurgaon|Kolkata|Ahmedabad)\b', text, re.IGNORECASE)
    return locations[0].title() if locations else ''

def extract_current_company(text):
    match = re.search(r'(?:currently|presently|working at|employed at)\s+([A-Z][a-zA-Z& ]+)', text, re.IGNORECASE)
    return match.group(1).strip() if match else ''

# ------------------- Similarity Scoring -------------------

def tfidf_similarity(jd_text, resume_text):
    vect = TfidfVectorizer()
    tfidf = vect.fit_transform([jd_text, resume_text])
    return cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0] * 100

def jaccard_similarity(jd_text, resume_text):
    a, b = set(tokenize(jd_text)), set(tokenize(resume_text))
    return (len(a & b) / len(a | b)) * 100 if a and b else 0

def keyword_match_score(jd_text, resume_text):
    jd_words = Counter(tokenize(jd_text))
    resume_words = Counter(tokenize(resume_text))
    common = set(jd_words.keys()) & set(resume_words.keys())
    return sum(min(jd_words[word], resume_words[word]) for word in common) / max(1, sum(jd_words.values())) * 100

def compute_combined_score(jd_text, resume_text):
    jd_clean = clean_text(jd_text)
    resume_clean = clean_text(resume_text)
    tfidf = tfidf_similarity(jd_clean, resume_clean)
    jaccard = jaccard_similarity(jd_clean, resume_clean)
    keyword = keyword_match_score(jd_clean, resume_clean)
    return round((0.5 * tfidf + 0.3 * jaccard + 0.2 * keyword), 2)

# ------------------- Streamlit UI -------------------

st.set_page_config(layout="wide")
st.title("🧠 Smart AI Hiring Assistant (Bulletproof Version)")
st.markdown("Upload Job Description and multiple resumes to compare & rank candidates without AI APIs.")

col1, col2 = st.columns(2)

with col1:
    company_name = st.text_input("🏢 Company Name")
    jd_file = st.file_uploader("📄 Upload Job Description (PDF, DOCX, TXT)", type=['pdf', 'docx', 'txt'])

with col2:
    resume_files = st.file_uploader("👤 Upload Candidate Resumes", type=['pdf', 'docx', 'txt'], accept_multiple_files=True)

if jd_file and resume_files:
    jd_text = extract_text(jd_file)
    data = []

    for resume in resume_files:
        resume_text = extract_text(resume)
        if not resume_text:
            continue
        filename = resume.name
        row = {
            'Name': extract_name_from_filename(filename),
            'Email': extract_email(resume_text),
            'Phone': extract_phone(resume_text),
            'Experience': extract_experience(resume_text),
            'Location': extract_location(resume_text),
            'Current Company': extract_current_company(resume_text),
            'JD-Resume Match %': compute_combined_score(jd_text, resume_text)
        }
        data.append(row)

    df = pd.DataFrame(data)
    df = df.sort_values(by='JD-Resume Match %', ascending=False)

    st.subheader("📊 Ranked Candidates")
    st.dataframe(df.reset_index(drop=True))

  from io import BytesIO

def convert_df(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    processed_data = output.getvalue()
    return processed_data

        return df.to_excel(index=False, engine='openpyxl')

    st.download_button("📥 Download Excel", data=convert_df(df), file_name="ranked_candidates.xlsx")

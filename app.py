import streamlit as st
import os
import base64
import re
import io
import pdfplumber
import docx2txt
import pandas as pd
import nltk
import string
nltk.download('punkt')


from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from nltk.corpus import stopwords, wordnet
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

# --- Ensure NLTK data is downloaded ---
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')
try:
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('wordnet')

# --- NLP Setup ---
lemmatizer = WordNetLemmatizer()
stop_words = set(stopwords.words('english'))

# --- Clean and preprocess text ---
def clean_text(text):
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    tokens = word_tokenize(text)
    tokens = [lemmatizer.lemmatize(word) for word in tokens if word not in stop_words]
    return ' '.join(tokens)

# --- Read Resume File ---
def extract_text_from_file(file):
    if file.name.endswith('.pdf'):
        with pdfplumber.open(file) as pdf:
            return ' '.join(page.extract_text() or '' for page in pdf.pages)
    elif file.name.endswith('.docx'):
        return docx2txt.process(file)
    elif file.name.endswith('.txt'):
        return file.read().decode('utf-8')
    else:
        return ''

# --- Extract Info ---
def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    return match.group(0) if match else ''

def extract_phone(text):
    match = re.search(r'\b\d{10}\b', text)
    return match.group(0) if match else ''

def extract_name(text, filename):
    lines = text.splitlines()
    for line in lines:
        words = line.strip().split()
        if 1 < len(words) <= 5:
            return line.strip().title()
    if "naukri_" in filename.lower():
        return filename.replace("naukri_", "").split('.')[0].replace('_', ' ').title()
    return "Name Not Found"

def extract_location(text):
    city_keywords = ['bangalore', 'hyderabad', 'mumbai', 'delhi', 'chennai', 'pune', 'gurgaon', 'noida', 'kolkata', 'lucknow']
    for word in text.lower().split():
        if word in city_keywords:
            return word.title()
    return ''

def extract_current_company(text):
    patterns = [r'currently working at (\w+)', r'presently working at (\w+)', r'current company[:\-]?\s*(\w+)']
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(1).title()
    return ''

def extract_experience(text):
    match = re.search(r'(\d+)\+?\s+years?', text.lower())
    return match.group(1) + ' years' if match else ''

# --- Similarity Score ---
def compute_combined_score(jd_text, resume_text):
    jd_clean = clean_text(jd_text)
    res_clean = clean_text(resume_text)

    tfidf = TfidfVectorizer()
    tfidf_matrix = tfidf.fit_transform([jd_clean, res_clean])
    cosine = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]

    set_jd = set(jd_clean.split())
    set_resume = set(res_clean.split())
    jaccard = len(set_jd & set_resume) / len(set_jd | set_resume)

    overlap = len(set_jd & set_resume) / len(set_jd) if set_jd else 0

    final_score = (0.5 * cosine + 0.3 * jaccard + 0.2 * overlap) * 100
    return round(final_score, 2)

# --- Generate Remarks ---
def generate_remarks(score, exp):
    try:
        exp_years = int(re.search(r'\d+', exp).group(0))
    except:
        exp_years = 0
    if score >= 80 and exp_years >= 5:
        return "Strong match for senior role"
    elif score >= 60:
        return "Good match"
    elif score >= 40:
        return "Average match"
    else:
        return "Weak match"

# --- Streamlit UI ---
st.set_page_config(page_title="Smart Hiring Assistant", layout="wide")
st.title("🧠 Smart AI Hiring Assistant (Non-AI Version)")

col1, col2 = st.columns(2)
with col1:
    company_name = st.text_input("Hiring For (Company Name):")

with col2:
    jd_file = st.file_uploader("Upload Job Description (PDF/DOCX/TXT)", type=['pdf', 'docx', 'txt'])

resume_files = st.file_uploader("Upload Resumes", type=['pdf', 'docx', 'txt'], accept_multiple_files=True)

if jd_file and resume_files:
    jd_text = extract_text_from_file(jd_file)
    jd_clean = clean_text(jd_text)
    results = []

    for resume in resume_files:
        text = extract_text_from_file(resume)
        clean_resume = clean_text(text)
        score = compute_combined_score(jd_clean, clean_resume)

        data = {
            'Name': extract_name(text, resume.name),
            'Email': extract_email(text),
            'Phone': extract_phone(text),
            'Experience': extract_experience(text),
            'Location': extract_location(text),
            'Current Company': extract_current_company(text),
            'Similarity %': score,
            'Remarks': generate_remarks(score, extract_experience(text)),
        }
        results.append(data)

    df = pd.DataFrame(results)
    df = df.sort_values(by='Similarity %', ascending=False).reset_index(drop=True)
    st.dataframe(df)

    # Download Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Results')
        writer.save()
    st.download_button("📥 Download Excel", output.getvalue(), file_name='Candidate_Ranking.xlsx')

else:
    st.info("Please upload both JD and Resumes to begin analysis.")

import streamlit as st
import os
import re
import docx2txt
import pdfplumber
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
from io import BytesIO

# ---------------------
# Helper Functions
# ---------------------

def extract_text_from_pdf(file):
    with pdfplumber.open(file) as pdf:
        return "\n".join([page.extract_text() or "" for page in pdf.pages])

def extract_text_from_docx(file):
    return docx2txt.process(file)

def extract_text(file):
    if file.name.endswith(".pdf"):
        return extract_text_from_pdf(file)
    elif file.name.endswith(".docx"):
        return extract_text_from_docx(file)
    elif file.name.endswith(".txt"):
        return file.read().decode("utf-8", errors="ignore")
    else:
        return ""

# ✅ Improved Name Extraction
def extract_name(text, filename="Unknown"):
    lines = text.strip().split("\n")[:30]
    possible_names = []

    blacklist = {'resume', 'curriculum', 'vitae', 'cv', 'product strategy', 'summary', 'contact', 'email', 'mobile', 'phone', 'experience'}

    for line in lines:
        line_clean = line.strip().lower()
        if any(word in line_clean for word in blacklist):
            continue

        line = line.strip()
        if 2 <= len(line.split()) <= 3 and all(word[0].isupper() for word in line.split() if word):
            possible_names.append(line.title())
            break

    if not possible_names:
        name_from_file = os.path.splitext(os.path.basename(filename))[0]
        name_from_file = name_from_file.lower().replace("naukri", "").replace("resume", "").replace("cv", "").strip()
        parts = re.findall(r'[a-zA-Z]+', name_from_file)
        if len(parts) >= 2:
            name = f"{parts[0].capitalize()} {parts[1].capitalize()}"
        elif len(parts) == 1:
            name = parts[0].capitalize()
        else:
            name = "Unknown"
        return name
    else:
        return possible_names[0]

def calculate_similarity(jd_text, resume_text):
    vectorizer = TfidfVectorizer(stop_words='english')
    vectors = vectorizer.fit_transform([jd_text, resume_text])
    return round(cosine_similarity(vectors[0:1], vectors[1:2])[0][0] * 100, 2)

# ---------------------
# Streamlit App
# ---------------------

st.set_page_config(page_title="Smart AI Hiring Assistant", layout="wide")
st.title("🤖 Smart AI Hiring Assistant")

company_name = st.text_input("🏢 Enter the Company Name for which you're hiring:")

col1, col2 = st.columns(2)

with col1:
    jd_file = st.file_uploader("📄 Upload Job Description (JD)", type=["pdf", "docx", "txt"])

with col2:
    resume_files = st.file_uploader("📂 Upload Resume(s)", accept_multiple_files=True, type=["pdf", "docx", "txt"])

if jd_file and resume_files:
    jd_text = extract_text(jd_file)

    candidate_data = []

    for resume in resume_files:
        resume_text = extract_text(resume)
        name = extract_name(resume_text, filename=resume.name)
        similarity = calculate_similarity(jd_text, resume_text)

        candidate_data.append({
            "Name": name,
            "Similarity (%)": similarity,
            "Filename": resume.name,
        })

    df = pd.DataFrame(candidate_data).sort_values(by="Similarity (%)", ascending=False).reset_index(drop=True)

    st.markdown("### 📊 Candidate Ranking")
    st.dataframe(df)

    def convert_df_to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Candidates")
        return output.getvalue()

    excel_data = convert_df_to_excel(df)
    st.download_button("📥 Download Excel", data=excel_data, file_name="ranked_candidates.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

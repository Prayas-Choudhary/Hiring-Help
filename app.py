import openai
import streamlit as st
import pandas as pd
from docx import Document
import pdfplumber
import os
import re
from io import BytesIO
from dotenv import load_dotenv
import json

# Load .env variables
load_dotenv()

# Set your OpenAI API key securely
openai.api_key = os.getenv("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") or st.secrets.get("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

# Extract text from DOCX
def extract_text_from_docx(docx_file):
    doc = Document(docx_file)
    return "\n".join([para.text for para in doc.paragraphs])

# Extract text from PDF
def extract_text_from_pdf(pdf_file):
    text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

# Extract basic fields
def extract_basic_fields(text):
    name_match = re.search(r"Name\s*[:\-]?\s*(.*)", text, re.IGNORECASE)
    email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    phone_match = re.search(r"\+?\d[\d\s\-]{8,15}", text)
    company_match = re.search(r"(?:Currently working at|Company)\s*[:\-]?\s*(.*)", text, re.IGNORECASE)
    notice_match = re.search(r"Notice Period\s*[:\-]?\s*(.*)", text, re.IGNORECASE)

    return {
        "Name": name_match.group(1).strip() if name_match else "",
        "Email": email_match.group(0) if email_match else "",
        "Phone": phone_match.group(0) if phone_match else "",
        "Current Company": company_match.group(1).strip() if company_match else "",
        "Notice Period": notice_match.group(1).strip() if notice_match else ""
    }

# AI function
def get_ai_review_and_similarity(jd_text, resume_text):
    prompt = f"""
Compare the following Job Description and Candidate Resume.

1. List the top 5 matching skills
2. List 3–5 missing or weak skills
3. Write a short review about the candidate's fitment for the job.
4. Estimate similarity percentage.

### Job Description:
{jd_text}

### Resume:
{resume_text}

Respond ONLY in JSON format like this:
{{
  "matching_skills": ["", "", "", "", ""],
  "missing_skills": ["", "", ""],
  "review": "short text",
  "similarity": "75%"
}}
"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        ai_output = response.choices[0].message.content.strip()
        result = json.loads(ai_output)
        return result
    except Exception as e:
        return {
            "matching_skills": [],
            "missing_skills": [],
            "review": f"AI error: {str(e)}",
            "similarity": "0%"
        }

# ------------------- Streamlit UI -------------------
st.title("🤖 Smart JD–Resume Matching Assistant")

jd_file = st.file_uploader("📄 Upload Job Description (PDF/DOCX/TXT)", type=["pdf", "docx", "txt"])
resumes = st.file_uploader("📁 Upload Resumes (PDF/DOCX)", type=["pdf", "docx"], accept_multiple_files=True)

if jd_file and resumes:
    # Read JD
    if jd_file.type == "application/pdf":
        jd_text = extract_text_from_pdf(jd_file)
    elif jd_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        jd_text = extract_text_from_docx(jd_file)
    else:
        jd_text = jd_file.read().decode()

    results = []

    for idx, resume in enumerate(resumes, 1):
        if resume.type == "application/pdf":
            resume_text = extract_text_from_pdf(resume)
        else:
            resume_text = extract_text_from_docx(resume)

        fields = extract_basic_fields(resume_text)
        ai_result = get_ai_review_and_similarity(jd_text, resume_text)

        results.append({
            "Sr. No.": idx,
            "Name": fields["Name"],
            "Email": fields["Email"],
            "Contact number": fields["Phone"],
            "Similarity of profile with JD(in %)": ai_result["similarity"],
            "Currently working at": fields["Current Company"],
            "Notice Period": fields["Notice Period"],
            "Reviews": ai_result["review"]
        })

    df = pd.DataFrame(results)

    st.success("✅ Processing Complete!")
    st.dataframe(df)

    # Excel download
    def convert_df(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        return output.getvalue()

    st.download_button("📥 Download Excel Report", data=convert_df(df), file_name="candidates_report.xlsx")


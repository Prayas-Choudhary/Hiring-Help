import os, re, base64
import pandas as pd
import fitz
import streamlit as st
from docx import Document
from io import BytesIO
from sentence_transformers import SentenceTransformer, util
import matplotlib.pyplot as plt
from fpdf import FPDF

model = SentenceTransformer('all-MiniLM-L6-v2')
st.set_page_config(page_title="AI Hiring Assistant", layout="wide")
STATUS_OPTIONS = ["Pending", "Shortlisted", "Interviewed", "Rejected"]

# Utility Functions
def extract_text(file):
    name = file.name.lower()
    if name.endswith('.pdf'):
        pdf = fitz.open(stream=file.read(), filetype="pdf")
        return "\n".join([page.get_text() for page in pdf])
    if name.endswith('.docx'):
        return "\n".join(p.text for p in Document(file).paragraphs)
    if name.endswith('.txt'):
        return file.read().decode()
    return ""

def extract_contact(text):
    email = re.findall(r'[\w\.-]+@[\w\.-]+', text)
    phone = re.findall(r'(?<!\d)(\d{10})(?!\d)', text)
    return (email[0] if email else "", phone[0] if phone else "")

def plot_skills_hist(df):
    return None  # placeholder

def to_pdf_report(df, company, jd_text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0,10,f"{company} - Candidate Summary", ln=True)
    pdf.set_font("Arial", size=12)
    for _, r in df.iterrows():
        pdf.cell(0,8,f"{r['Name']} | {r['Similarity %']}% | {r['Status']}", ln=True)
    return pdf.output(dest='S').encode('latin1')

def generate_email(name, jd_text):
    clean = "\n".join([l for l in jd_text.splitlines() if 'client' not in l.lower()])
    return f"Hi {name},\n\nWe found your background a strong match:\n\n{clean}\n\nRegards,\nTeam"

# UI
st.title("🧠 Smart AI Hiring Assistant")
company = st.text_input("🏢 Company Name")
jd_files = st.file_uploader("📄 Upload JD(s)", type=['pdf','docx','txt'], accept_multiple_files=True)
resume_files = st.file_uploader("📁 Upload Resume(s)", type=['pdf','docx'], accept_multiple_files=True)

if jd_files and resume_files and company:
    jds = {f.name: extract_text(f) for f in jd_files}
    jd_choice = st.selectbox("Select Active JD", list(jds.keys()))
    jd_text = jds[jd_choice]
    st.text_area("JD Preview", jd_text, height=200)

    jd_embed = model.encode(jd_text, convert_to_tensor=True)
    seen = set(); rows=[]
    for f in resume_files:
        text = extract_text(f)
        email, phone = extract_contact(text)
        key = (os.path.splitext(f.name)[0], email)
        if key in seen: continue
        seen.add(key)
        name = os.path.splitext(f.name)[0]
        skills = ["python","java","sql","aws","excel"]  # sample
        resume_skills = [k for k in skills if k in text.lower()]
        missing = [k for k in skills if k not in resume_skills]
        emb = model.encode(text, convert_to_tensor=True)
        sim = util.cos_sim(emb, jd_embed).item()*100
        rows.append({
            "Name": name, "Email": email, "Phone": phone,
            "Match %": round(sim,2),
            "Skills": ", ".join(resume_skills),
            "Missing": ", ".join(missing),
            "Resume": text[:300]+"...",
            "Status": "Pending",
            "EmailDraft": generate_email(name, jd_text)
        })

    df = pd.DataFrame(rows).sort_values("Match %", ascending=False).reset_index(drop=True)
    st.dataframe(df)

    for i in range(len(df)):
        df.at[i,"Status"] = st.selectbox(f"Status for {df.at[i,'Name']}", STATUS_OPTIONS, key=i)
        st.text_area(f"📧 Email Draft - {df.at[i,'Name']}", df.at[i,"EmailDraft"], height=100, key=f"ed{i}")
        st.write("---")

    buf = BytesIO(); df.to_excel(buf, index=False, engine='openpyxl'); buf.seek(0)
    st.download_button("⬇ Download Excel", data=buf, file_name=f"{company}_candidates.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    pdfdata = to_pdf_report(df, company, jd_text)
    st.download_button("📄 Download PDF Report", data=pdfdata, file_name="report.pdf", mime="application/pdf")

import streamlit as st
import os
from dotenv import load_dotenv
import openai
import plotly.graph_objects as go
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image
import json
import random
import requests
from bs4 import BeautifulSoup
from ast import literal_eval

# ---------------- Load API Key ----------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# ---------------- Streamlit UI ----------------
st.title("CareerCraft AI — Dynamic Resume Tailor with PDF Export")

# Resume & Job Description Input
st.header("Paste your current resume or CV")
resume_text = st.text_area("Resume Text", height=300)
st.header("Job Description to Target")
job_desc = st.text_area("Job Description", height=200)

# Optional: Auto-skill extraction
st.header("Optional: Auto-Skill Extraction")
github_username = st.text_input("GitHub Username")
linkedin_url = st.text_input("LinkedIn Profile URL (public)")

num_versions = st.slider("Number of Resume Versions", 1, 3, 2)
candidate_name = st.text_input("Candidate Name", "Candidate")

# ---------------- Skill Extraction ----------------
def extract_github_skills(username):
    if not username:
        return []
    url = f"https://github.com/{username}?tab=repositories"
    try:
        res = requests.get(url)
        soup = BeautifulSoup(res.text, "html.parser")
        langs = [l.text.strip() for l in soup.select("span[itemprop=programmingLanguage]")]
        return list(set(langs))
    except:
        return []

def extract_linkedin_skills(profile_url):
    if not profile_url:
        return []
    try:
        res = requests.get(profile_url)
        soup = BeautifulSoup(res.text, "html.parser")
        skills = [s.text.strip() for s in soup.select(".pv-skill-category-entity__name-text")]
        return list(set(skills))
    except:
        return []

all_extracted_skills = list(set(extract_github_skills(github_username) + extract_linkedin_skills(linkedin_url)))

# ---------------- PDF Generation Function ----------------
def create_pdf(versions, charts, candidate_name="Candidate"):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Cover Page
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawCentredString(width / 2, height - 100, "CareerCraft AI Tailored Resumes")
    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(width / 2, height - 130, f"Candidate: {candidate_name}")
    pdf.showPage()

    for idx, v in enumerate(versions):
        y_pos = height - 50
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(50, y_pos, f"Tailored Resume Version {idx+1}")
        y_pos -= 30

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y_pos, "Top Skills Aligned:")
        pdf.setFont("Helvetica", 12)
        pdf.drawString(200, y_pos, ", ".join(v["selected_skills"]))
        y_pos -= 20

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y_pos, "Fit Score:")
        pdf.setFont("Helvetica", 12)
        pdf.drawString(200, y_pos, f"{v['fit_score']}/100")
        y_pos -= 20

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y_pos, "Skill Gaps & Learning Paths:")
        y_pos -= 15
        pdf.setFont("Helvetica", 12)
        for skill, path in zip(v["missing_skills"], v["learning_paths"]):
            if y_pos < 50:
                pdf.showPage()
                y_pos = height - 50
            pdf.drawString(60, y_pos, f"- {skill}: {path}")
            y_pos -= 15

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y_pos, "Improved Bullets:")
        y_pos -= 15
        pdf.setFont("Helvetica", 12)
        for line in v["version_text"].splitlines():
            if y_pos < 50:
                pdf.showPage()
                y_pos = height - 50
            pdf.drawString(60, y_pos, line)
            y_pos -= 12

        # Insert chart if available
        if charts[idx]:
            chart_img = charts[idx]
            chart_img.seek(0)
            img = Image.open(chart_img)
            pdf.showPage()
            pdf.drawInlineImage(img, 50, height/2-150, width=500, height=300)

        pdf.showPage()

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer

# ---------------- Tailored Resume Generator ----------------
def generate_tailored_resume(resume_text, job_desc, extracted_skills=None, mock_mode=False):
    if mock_mode or not openai.api_key:
        # Mock fallback
        skills_pool = extracted_skills if extracted_skills else ["Python", "Java", "Kotlin", "Apex", "React.js", "AWS", "Azure", "Data Analysis", "Communication"]
        selected_skills = random.sample(skills_pool, k=min(3, len(skills_pool)))
        fit_score = random.randint(70, 95)
        missing_skills = random.sample([s for s in skills_pool if s not in selected_skills], k=min(2, len(skills_pool)-len(selected_skills)))
        learning_paths = [f"Take a course on {skill}" for skill in missing_skills]
        bullets = [f"- {line[:50]}... [Improved]" for line in resume_text.splitlines() if line.strip()]
        version_text = (
            f"[Mocked Tailored Resume]\n\n"
            f"Top Skills Aligned: {', '.join(selected_skills)}\n\n"
            f"Improved Bullets:\n" + "\n".join(bullets[:5]) + "\n\n"
            f"Fit Score for Job: {fit_score}/100\n\n"
            f"Skill Gaps: {', '.join(missing_skills)}\n"
            f"Recommended Learning Path:\n" + "\n".join(learning_paths)
        )
        return {"version_text": version_text,"selected_skills": selected_skills,"fit_score": fit_score,"missing_skills": missing_skills,"learning_paths": learning_paths}

    skills_hint = ""
    if extracted_skills:
        skills_hint = "\n\nAvailable skills from GitHub/LinkedIn: " + ", ".join(extracted_skills)

    prompt = f"""
You are a professional career coach AI.
Given the resume and job description below, generate a tailored resume version.
STRICTLY OUTPUT VALID JSON, no extra text, no commentary.

Output format:
{{
  "version_text": "Tailored resume text",
  "selected_skills": ["skill1", "skill2"],
  "fit_score": 0-100,
  "missing_skills": ["skill1", "skill2"],
  "learning_paths": ["recommended learning path for skill1", "recommended learning path for skill2"]
}}

Resume:
{resume_text}

Job Description:
{job_desc}

{skills_hint}
"""
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        result_text = response.choices[0].message.content.strip()
        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            return literal_eval(result_text)
    except (openai.error.RateLimitError, openai.error.OpenAIError, json.JSONDecodeError, ValueError):
        st.warning("OpenAI returned an error or invalid JSON. Using mock mode.")
        return generate_tailored_resume(resume_text, job_desc, extracted_skills=extracted_skills, mock_mode=True)

# ---------------- Main Process ----------------
if st.button("Tailor Resume"):
    if resume_text and job_desc:
        tailored_versions = []
        chart_images = []

        for i in range(num_versions):
            st.info(f"Generating version {i+1}...")
            v = generate_tailored_resume(resume_text, job_desc, extracted_skills=all_extracted_skills)
            tailored_versions.append(v)

            # Skill-gap chart
            if v["missing_skills"]:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=v["missing_skills"],
                    y=[1]*len(v["missing_skills"]),
                    text=v["learning_paths"],
                    textposition="outside",
                    marker_color="blue"
                ))
                fig.update_layout(title=f"Career Roadmap Version {i+1}", yaxis=dict(visible=False), height=300)
                chart_img = BytesIO()
                fig.write_image(chart_img, format="png")
                chart_images.append(chart_img)
            else:
                chart_images.append(None)

        # Display
        for idx, v in enumerate(tailored_versions):
            st.subheader(f"Tailored Resume Version {idx+1}")
            st.text_area(f"Result {idx+1}", v["version_text"], height=500)

        # PDF Download
        pdf_buffer = create_pdf(tailored_versions, chart_images, candidate_name)
        st.download_button(
            label="Download All Versions as Professional PDF",
            data=pdf_buffer,
            file_name="CareerCraft_Resumes.pdf",
            mime="application/pdf"
        )
    else:
        st.warning("Please enter both your resume and a job description.")

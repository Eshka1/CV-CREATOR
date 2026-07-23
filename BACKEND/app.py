 import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect
from dotenv import load_dotenv
from google import genai

# Load the API key from the .env file
load_dotenv()

app = Flask(__name__)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
import database as db        # ADD THIS
db.init_db()
# You can swap this for "gemma-4-26b-a4b-it" or "gemma-4-31b-it" if you want
# a smarter (but slower) model. 12b is the fast/reliable choice for a demo.
MODEL = "gemma-4-26b-a4b-it"

PROFILES_FILE = "profiles.json"


def call_gemma(system_instruction, user_content):
    """Sends one prompt to Gemma 4 and returns its text reply."""
    response = client.models.generate_content(
        model=MODEL,
        contents=user_content,
        config={"system_instruction": system_instruction},
    )
    return response.text


def clean_json(text):
    """Gemma sometimes wraps JSON in ```json fences. Strip those before parsing."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def organize_profile(raw):
    """Sub-phase 1.3: turn messy raw text into clean structured JSON."""
    system = (
        "You organize raw, messy career profile text into clean JSON. "
        "Return ONLY valid JSON with this exact shape, no extra text, no markdown fences:\n"
        '{"personal": {"name": "", "email": "", "location": ""}, '
        '"education": [{"school": "", "degree": "", "year": ""}], '
        '"experience": [{"role": "", "company": "", "duration": "", "description": ""}], '
        '"skills": [""], '
        '"projects": [{"title": "", "description": ""}], '
        '"certificates": [""]}\n'
        "Split freeform text into separate list items sensibly. "
        "If information is missing, leave that field as an empty string, don't invent it."
    )
    text = call_gemma(system, json.dumps(raw))
    return clean_json(text)


def rewrite_profile(profile):
    """Sub-phase 1.4: rewrite descriptions into professional resume bullets."""
    system = (
        "Rewrite each 'description' field under experience and projects into a "
        "single professional, achievement-oriented resume bullet. Use strong action "
        "verbs. Do not invent facts or numbers that aren't implied by the input. "
        "Return the SAME JSON structure back, only the description fields changed. "
        "No extra text, no markdown fences."
    )
    text = call_gemma(system, json.dumps(profile))
    return clean_json(text)


def save_profile(profile):
    """Sub-phase 1.5: save as the master record in profiles.json."""
    all_profiles = []
    if os.path.exists(PROFILES_FILE):
        with open(PROFILES_FILE) as f:
            try:
                all_profiles = json.load(f)
            except json.JSONDecodeError:
                all_profiles = []
    all_profiles.append(profile)
    with open(PROFILES_FILE, "w") as f:
        json.dump(all_profiles, f, indent=2)


@app.route("/")
def home():
    return render_template("profile_form.html")


@app.route("/submit-profile", methods=["POST"])
def submit_profile():
    # Sub-phase 1.2: collect the raw form input, no cleaning done here on purpose
    raw = {
        "name": request.form.get("name", ""),
        "email": request.form.get("email", ""),
        "location": request.form.get("location", ""),
        "education_raw": request.form.get("education", ""),
        "experience_raw": request.form.get("ex+perience", ""),
        "skills_raw": request.form.get("skills", ""),
        "projects_raw": request.form.get("projects", ""),
        "certificates_raw": request.form.get("certificates", ""),
    }

    organized = organize_profile(raw)
    final_profile = rewrite_profile(organized)
    save_profile(final_profile)

    return render_template("profile_done.html", profile=final_profile)
def load_latest_profile():
    if not os.path.exists(PROFILES_FILE):
        return None
    with open(PROFILES_FILE) as f:
        profiles = json.load(f)
    return profiles[-1] if profiles else None


def generate_summary(profile, target=""):
    system = (
        "Write a 2-3 sentence professional resume summary for this candidate. "
        "Confident, achievement-focused, no clichés. "
        + (f"Tailor it toward a role at {target}. " if target else "")
        + "Return ONLY the summary text, no labels, no quotes, no markdown."
    )
    return call_gemma(system, json.dumps(profile)).strip()


def generate_about_me(profile):
    system = (
        "Write a warm, first-person 'About Me' paragraph (3-4 sentences) for a "
        "portfolio website, based on this profile. Professional but personable. "
        "Return ONLY the paragraph text, no labels, no markdown."
    )
    return call_gemma(system, json.dumps(profile)).strip()


@app.route("/resume")
def resume():
    profile = load_latest_profile()
    if not profile:
        return "No profile yet — fill out the form first.", 400
    target = request.args.get("target", "")
    summary = generate_summary(profile, target)
    return render_template("resume.html", profile=profile, summary=summary, target=target)


@app.route("/portfolio")
def portfolio():
    profile = load_latest_profile()
    if not profile:
        return "No profile yet — fill out the form first.", 400
    about_me = generate_about_me(profile)
    return render_template("portfolio.html", profile=profile, about_me=about_me)
SAVED_JOBS_FILE = "saved_jobs.json"

# 3.1 — Seed job data. Just a hardcoded Python list, no database needed today.
JOBS = [
    {"id": 1, "title": "Junior Backend Developer", "company": "Nexora Tech", "industry": "Technology",
     "location": "Dhaka", "remote": "On-site", "experience": "Entry", "salary": "৳40,000–55,000/mo",
     "required_skills": ["Python", "Flask", "SQL"],
     "description": "Build and maintain backend APIs for our internal tools team."},
    {"id": 2, "title": "Data Analyst", "company": "Brightline Analytics", "industry": "Technology",
     "location": "Remote", "remote": "Remote", "experience": "Entry", "salary": "৳35,000–50,000/mo",
     "required_skills": ["SQL", "Excel", "Python"],
     "description": "Analyze customer data and build dashboards for stakeholders."},
    {"id": 3, "title": "Frontend Developer", "company": "Pixel Foundry", "industry": "Technology",
     "location": "Dhaka", "remote": "On-site", "experience": "Entry", "salary": "৳38,000–52,000/mo",
     "required_skills": ["JavaScript", "React", "CSS"],
     "description": "Build customer-facing web interfaces alongside a small design team."},
    {"id": 4, "title": "Marketing Coordinator", "company": "LoudSpeak Media", "industry": "Marketing",
     "location": "Remote", "remote": "Remote", "experience": "Entry", "salary": "৳30,000–42,000/mo",
     "required_skills": ["Content Writing", "SEO", "Social Media"],
     "description": "Plan and run social campaigns for consumer brand clients."},
    {"id": 5, "title": "Financial Analyst", "company": "Cedarpoint Capital", "industry": "Finance",
     "location": "New York", "remote": "On-site", "experience": "Entry", "salary": "$55,000–65,000/yr",
     "required_skills": ["Excel", "Financial Modeling", "SQL"],
     "description": "Support the investment team with quarterly financial models."},
    {"id": 6, "title": "QA Engineer", "company": "Nexora Tech", "industry": "Technology",
     "location": "Remote", "remote": "Remote", "experience": "Entry", "salary": "৳36,000–48,000/mo",
     "required_skills": ["Python", "Testing", "SQL"],
     "description": "Write automated tests and track bugs across our product suite."},
    {"id": 7, "title": "UX Designer", "company": "Pixel Foundry", "industry": "Design",
     "location": "Remote", "remote": "Remote", "experience": "Mid", "salary": "৳55,000–70,000/mo",
     "required_skills": ["Figma", "UX Research", "Prototyping"],
     "description": "Design flows and prototypes for our mobile app redesign."},
    {"id": 8, "title": "Healthcare Data Assistant", "company": "MediTrack", "industry": "Healthcare",
     "location": "Dhaka", "remote": "On-site", "experience": "Entry", "salary": "৳32,000–45,000/mo",
     "required_skills": ["Excel", "Data Entry", "SQL"],
     "description": "Maintain patient record datasets and generate weekly reports."},
    {"id": 9, "title": "Junior Python Developer", "company": "Brightline Analytics", "industry": "Technology",
     "location": "Dhaka", "remote": "On-site", "experience": "Entry", "salary": "৳40,000–52,000/mo",
     "required_skills": ["Python", "Flask", "APIs"],
     "description": "Build internal automation scripts and small Flask services."},
    {"id": 10, "title": "Sales Development Rep", "company": "LoudSpeak Media", "industry": "Marketing",
     "location": "Remote", "remote": "Remote", "experience": "Entry", "salary": "৳28,000–40,000/mo + comm.",
     "required_skills": ["Communication", "CRM Tools", "Cold Outreach"],
     "description": "Generate and qualify leads for the sales team."},
    {"id": 11, "title": "Mid-level Backend Engineer", "company": "Cedarpoint Capital", "industry": "Finance",
     "location": "New York", "remote": "Remote", "experience": "Mid", "salary": "$75,000–90,000/yr",
     "required_skills": ["Python", "SQL", "System Design"],
     "description": "Own backend services powering internal trading tools."},
    {"id": 12, "title": "Graphic Designer", "company": "LoudSpeak Media", "industry": "Design",
     "location": "Dhaka", "remote": "On-site", "experience": "Entry", "salary": "৳30,000–42,000/mo",
     "required_skills": ["Adobe Photoshop", "Illustrator", "Branding"],
     "description": "Design campaign assets for client social and print media."},
]

db.seed_jobs_if_empty(JOBS)

def load_saved_job_ids():
    if not os.path.exists(SAVED_JOBS_FILE):
        return []
    with open(SAVED_JOBS_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_job_id(job_id):
    saved = load_saved_job_ids()
    if job_id not in saved:
        saved.append(job_id)
    with open(SAVED_JOBS_FILE, "w") as f:
        json.dump(saved, f)


# 3.4 — AI recommendations. Gemma 4 picks the 3 best matches for the latest profile.
def get_job_recommendations(profile, jobs):
    system = (
        "Given a candidate's skills and a list of jobs (id, title, company, "
        "required_skills), pick the 3 best-matching job ids for this candidate. "
        "Return ONLY valid JSON: a list like "
        '[{"id": 3, "title": "Frontend Developer", "reason": "one short sentence why"}]. '
        "No extra text, no markdown fences."
    )
    jobs_summary = [
        {"id": j["id"], "title": j["title"], "company": j["company"], "required_skills": j["required_skills"]}
        for j in jobs
    ]
    content = json.dumps({"candidate_skills": profile.get("skills", []), "jobs": jobs_summary})
    try:
        text = call_gemma(system, content)
        return clean_json(text)
    except Exception:
        return []  # if Gemma hiccups, just show no recommendations instead of crashing the page


@app.route("/jobs")
def browse_jobs():
    industry = request.args.get("industry", "")
    location = request.args.get("location", "")
    experience = request.args.get("experience", "")
    remote = request.args.get("remote", "")

    filtered = JOBS
    if industry:
        filtered = [j for j in filtered if j["industry"] == industry]
    if location:
        filtered = [j for j in filtered if j["location"] == location]
    if experience:
        filtered = [j for j in filtered if j["experience"] == experience]
    if remote:
        filtered = [j for j in filtered if j["remote"] == remote]

    saved_ids = load_saved_job_ids()
    profile = load_latest_profile()
    recommendations = get_job_recommendations(profile, JOBS) if profile else []

    return render_template(
        "jobs.html",
        jobs=filtered,
        saved_ids=saved_ids,
        recommendations=recommendations,
        industries=sorted(set(j["industry"] for j in JOBS)),
        locations=sorted(set(j["location"] for j in JOBS)),
        experiences=sorted(set(j["experience"] for j in JOBS)),
        filters={"industry": industry, "location": location, "experience": experience, "remote": remote},
    )


@app.route("/jobs/save/<int:job_id>")
def save_job(job_id):
    save_job_id(job_id)
    return redirect("/jobs")


@app.route("/jobs/saved")
def saved_jobs():
    saved_ids = load_saved_job_ids()
    jobs = [j for j in JOBS if j["id"] in saved_ids]
    return render_template("saved_jobs.html", jobs=jobs)
APPLICATIONS_FILE = "applications.json"


# 4.1 — Skill-gap analysis. Plain Python, no AI needed for the raw comparison —
# fast and 100% consistent, which matters more than cleverness here.
def compute_skill_gap(profile_skills, job_skills):
    profile_lower = [s.strip().lower() for s in profile_skills]
    matched = [s for s in job_skills if s.strip().lower() in profile_lower]
    missing = [s for s in job_skills if s.strip().lower() not in profile_lower]
    score = round(len(matched) / len(job_skills) * 100) if job_skills else 100
    return matched, missing, score


# 4.2 — Gemma 4 explains the score in plain, encouraging language
def generate_readiness_narrative(job, matched, missing, score):
    system = (
        "In 2-3 sentences, explain this readiness score to the candidate in plain, "
        "encouraging language: what they already have going for them, and what's missing. "
        "Return ONLY the explanation text, no markdown."
    )
    content = json.dumps({"job_title": job["title"], "score": score, "matched_skills": matched, "missing_skills": missing})
    return call_gemma(system, content).strip()


# 4.3 — Gemma 4 generates the tailored cover letter and email
def generate_cover_letter(profile, job):
    system = (
        "Write a professional, concise cover letter (3-4 paragraphs) for this candidate "
        "applying to this specific job. Reference relevant skills and projects from their "
        "profile that match the job's required skills. Do not invent experience not in the "
        "profile. Return ONLY the cover letter text, no labels, no markdown."
    )
    content = json.dumps({"profile": profile, "job": job})
    return call_gemma(system, content).strip()


def generate_application_email(profile, job):
    system = (
        "Write a short, professional application email (4-6 sentences) that the candidate "
        "could send to accompany their application. Mention the specific role and company. "
        "Return ONLY the email text including a greeting and sign-off, no subject line, no markdown."
    )
    content = json.dumps({"profile": profile, "job": job})
    return call_gemma(system, content).strip()


# 4.4 — Application workspace: one saved record per job application
def load_applications():
    if not os.path.exists(APPLICATIONS_FILE):
        return []
    with open(APPLICATIONS_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_application(app_record):
    apps = load_applications()
    apps = [a for a in apps if a["job_id"] != app_record["job_id"]]
    apps.append(app_record)
    with open(APPLICATIONS_FILE, "w") as f:
        json.dump(apps, f, indent=2)


@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    job = next((j for j in JOBS if j["id"] == job_id), None)
    if not job:
        return "Job not found", 404
    profile = load_latest_profile()
    if not profile:
        return "No profile yet — fill out the form first.", 400

    matched, missing, score = compute_skill_gap(profile.get("skills", []), job["required_skills"])
    narrative = generate_readiness_narrative(job, matched, missing, score)
    applications = load_applications()
    already_applied = any(a["job_id"] == job_id for a in applications)

    return render_template(
        "job_detail.html", job=job, score=score, matched=matched, missing=missing,
        narrative=narrative, already_applied=already_applied,
    )


# 4.5 — One-click apply: generates everything and saves it in one step
@app.route("/jobs/<int:job_id>/apply")
def apply_to_job(job_id):
    job = next((j for j in JOBS if j["id"] == job_id), None)
    if not job:
        return "Job not found", 404
    profile = load_latest_profile()
    if not profile:
        return "No profile yet — fill out the form first.", 400

    matched, missing, score = compute_skill_gap(profile.get("skills", []), job["required_skills"])
    cover_letter = generate_cover_letter(profile, job)
    email = generate_application_email(profile, job)

    app_record = {
        "job_id": job_id,
        "job_title": job["title"],
        "company": job["company"],
        "status": "Applied",
        "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "readiness_score": score,
        "cover_letter": cover_letter,
        "email": email,
    }
    save_application(app_record)
    return redirect(f"/applications/{job_id}")


@app.route("/applications")
def applications_list():
    apps = load_applications()
    return render_template("applications.html", applications=apps)


@app.route("/applications/<int:job_id>")
def application_detail(job_id):
    apps = load_applications()
    application = next((a for a in apps if a["job_id"] == job_id), None)
    if not application:
        return "No application found for this job yet.", 404
    return render_template("application_detail.html", application=application)

if __name__ == "__main__":
    app.run(debug=True, port=5000)


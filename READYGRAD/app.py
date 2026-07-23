import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, url_for
from dotenv import load_dotenv
from google import genai
import database as db
import random

# Load the API key from the .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = "readygrad-secret-key-998877"
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

db.init_db() 

MODEL = "gemini-2.5-flash"

PROFILES_FILE = "profiles.json"
USERS_FILE = "users.json"
CREATED_CVS_FILE = "created_cvs.json"
SAVED_JOBS_FILE = "saved_jobs.json"
APPLICATIONS_FILE = "applications.json"


def call_gemma(system_instruction, user_content):
    """Sends one prompt to Gemini and returns its text reply."""
    response = client.models.generate_content(
        model=MODEL,
        contents=user_content,
        config={"system_instruction": system_instruction},
    )
    return response.text


def clean_json(text):
    """Gemini sometimes wraps JSON in ```json fences. Strip those before parsing."""
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
    try:
        text = call_gemma(system, json.dumps(raw))
        return clean_json(text)
    except Exception as e:
        print(f"Error in organize_profile using Gemini API: {e}")
        # Build manual structured dict from raw input form values safely
        skills_raw = raw.get("skills_raw") or ""
        certs_raw = raw.get("certificates_raw") or ""
        edu_raw = raw.get("education_raw") or ""
        exp_raw = raw.get("experience_raw") or ""
        proj_raw = raw.get("projects_raw") or ""

        skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
        certs = [c.strip() for c in certs_raw.split(",") if c.strip()]
        
        edu_list = []
        for line in edu_raw.split("\n"):
            line = line.strip()
            if line:
                parts = [p.strip() for p in line.split("-") if p.strip()]
                school = parts[0] if len(parts) > 0 else line
                degree = parts[1] if len(parts) > 1 else "Degree/Studies"
                year = parts[2] if len(parts) > 2 else ""
                edu_list.append({"school": school, "degree": degree, "year": year})
                
        exp_list = []
        for line in exp_raw.split("\n"):
            line = line.strip()
            if line:
                parts = [p.strip() for p in line.split("-") if p.strip()]
                role = parts[0] if len(parts) > 0 else line
                company = parts[1] if len(parts) > 1 else "Company"
                duration = parts[2] if len(parts) > 2 else ""
                description = parts[3] if len(parts) > 3 else "Professional experience details"
                exp_list.append({"role": role, "company": company, "duration": duration, "description": description})
                
        proj_list = []
        for line in proj_raw.split("\n"):
            line = line.strip()
            if line:
                parts = [p.strip() for p in line.split("-") if p.strip()]
                title = parts[0] if len(parts) > 0 else line
                desc = parts[1] if len(parts) > 1 else "Project details"
                proj_list.append({"title": title, "description": desc})
                
        return {
            "personal": {
                "name": raw.get("name", ""),
                "email": raw.get("email", ""),
                "location": raw.get("location", "")
            },
            "education": edu_list or [{"school": edu_raw, "degree": "Degree", "year": ""}] if edu_raw else [],
            "experience": exp_list or [{"role": exp_raw, "company": "Company", "duration": "", "description": exp_raw}] if exp_raw else [],
            "skills": skills or ["Python", "Flask", "SQL"],
            "projects": proj_list or [{"title": "Portfolio Project", "description": proj_raw}] if proj_raw else [],
            "certificates": certs
        }


def rewrite_profile(profile):
    """Sub-phase 1.4: rewrite descriptions into professional resume bullets."""
    system = (
        "Rewrite each 'description' field under experience and projects into a "
        "single professional, achievement-oriented resume bullet. Use strong action "
        "verbs. Do not invent facts or numbers that aren't implied by the input. "
        "Return the SAME JSON structure back, only the description fields changed. "
        "No extra text, no markdown fences."
    )
    try:
        text = call_gemma(system, json.dumps(profile))
        return clean_json(text)
    except Exception as e:
        print(f"Error in rewrite_profile: {e}")
        return profile


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
    try:
        db.save_profile_db(profile)
    except Exception as e:
        print(f"Database sync warning in save_profile: {e}")


USERS_FILE = "users.json"


def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def get_user_profile(email):
    if not os.path.exists(PROFILES_FILE):
        return None
    with open(PROFILES_FILE) as f:
        try:
            profiles = json.load(f)
        except json.JSONDecodeError:
            profiles = []
    # Look for profile matching email
    for p in reversed(profiles):
        if p.get("personal", {}).get("email", "").strip().lower() == email.strip().lower():
            return p
    return None


@app.route("/")
def home():
    user = session.get("user")
    return render_template("index.html", user=user)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("user"):
        return redirect(url_for("dashboard"))
    
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()
        
        if not name or not email or not phone or not password:
            error = "All fields are required."
        else:
            users = load_users()
            if email in users:
                error = "An account with this email already exists."
            else:
                users[email] = {
                    "name": name,
                    "phone": phone,
                    "password": password
                }
                save_users(users)
                session["user"] = {
                    "name": name,
                    "email": email,
                    "phone": phone
                }
                return redirect(url_for("dashboard"))
                
    return render_template("auth.html", mode="signup", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect(url_for("dashboard"))
        
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        
        if not email or not password:
            error = "Email and password are required."
        else:
            users = load_users()
            if email in users and users[email]["password"] == password:
                session["user"] = {
                    "name": users[email]["name"],
                    "email": email,
                    "phone": users[email]["phone"]
                }
                return redirect(url_for("dashboard"))
            else:
                error = "Invalid email or password."
                
    return render_template("auth.html", mode="login", error=error)


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))


@app.route("/dashboard")
def dashboard():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
        
    profile = get_user_profile(user["email"])
    saved_ids = load_saved_job_ids(user["email"])
    apps = load_applications()
    applications = [a for a in apps if a.get("user_email") == user["email"] or a.get("user_email") is None]
    
    # Calculate status breakdown
    applied_count = sum(1 for a in applications if a["status"] == "Applied")
    in_process_count = sum(1 for a in applications if a["status"] == "In Process")
    accepted_count = sum(1 for a in applications if a["status"] == "Accepted")
    denied_count = sum(1 for a in applications if a["status"] == "Denied")
    
    recommendations = []
    if profile:
        recommendations = get_job_recommendations(profile, JOBS)
        for rec in recommendations:
            job = next((j for j in JOBS if j["id"] == rec.get("id")), None)
            if job:
                _, _, score = compute_skill_gap(profile.get("skills", []), job["required_skills"])
                rec["score"] = score
            else:
                rec["score"] = 0
        
    # Calculate profile completeness
    completion = 0
    checklist = {
        "signup": True,
        "profile": False,
        "jobs": False,
        "resume": False,
        "portfolio": False
    }
    
    if profile:
        checklist["profile"] = True
        completion += 25
        
        if profile.get("skills"):
            completion += 25
        if profile.get("experience"):
            completion += 25
        if profile.get("projects") or profile.get("education"):
            completion += 25
            
    if saved_ids:
        checklist["jobs"] = True
    if applications:
        checklist["resume"] = True
        checklist["portfolio"] = True
        
    completion = min(100, completion)
    if completion == 0:
        completion = 20 # signup is done
        
    return render_template(
        "dashboard.html",
        user=user,
        profile=profile,
        jobs=JOBS,
        saved_ids=saved_ids,
        applications=applications,
        recommendations=recommendations[:4],
        completion=completion,
        checklist=checklist,
        applied_count=applied_count,
        in_process_count=in_process_count,
        accepted_count=accepted_count,
        denied_count=denied_count
    )
@app.route("/build-profile")
def build_profile_page():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    profile = get_user_profile(user["email"])
    edit_mode = request.args.get("edit", "").lower() == "true"
    if profile and not edit_mode:
        return render_template("profile_dashboard.html", user=user, profile=profile)
    return render_template("profile_form.html", user=user, profile=profile)


@app.route("/submit-profile", methods=["POST"])
def submit_profile():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
        
    raw = {
        "name": request.form.get("name", "").strip(),
        "email": user["email"],
        "location": request.form.get("location", "").strip(),
        "education_raw": request.form.get("education", "").strip(),
        "experience_raw": request.form.get("experience", "").strip(),
        "skills_raw": request.form.get("skills", "").strip(),
        "projects_raw": request.form.get("projects", "").strip(),
        "certificates_raw": request.form.get("certificates", "").strip(),
    }

    # Handle file upload for profile picture
    avatar_file = request.files.get("avatar")
    avatar_url = None
    if avatar_file and avatar_file.filename:
        # ensure uploads folder exists in static
        upload_dir = os.path.join(app.root_path, "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        # Create safe, unique filename based on user email
        safe_email = user["email"].replace("@", "_").replace(".", "_")
        filename = f"profile_{safe_email}_{avatar_file.filename}"
        filepath = os.path.join(upload_dir, filename)
        avatar_file.save(filepath)
        avatar_url = f"/static/uploads/{filename}"

    # Load existing profile to preserve data if necessary
    existing_profile = get_user_profile(user["email"])

    # Check if there is any data beyond location
    has_data = any([
        raw["education_raw"],
        raw["experience_raw"],
        raw["skills_raw"],
        raw["projects_raw"],
        raw["certificates_raw"]
    ])

    if not has_data:
        # Create simple profile
        final_profile = {
            "personal": {
                "name": raw["name"] or user["name"],
                "email": user["email"],
                "location": raw["location"]
            },
            "education": [],
            "experience": [],
            "skills": [],
            "projects": [],
            "certificates": []
        }
    else:
        organized = organize_profile(raw)
        final_profile = rewrite_profile(organized)

    # Force profile email to match user email
    final_profile["personal"]["email"] = user["email"]
    if not final_profile["personal"].get("name"):
        final_profile["personal"]["name"] = raw["name"] or user["name"]

    # Set avatar URL
    if avatar_url:
        final_profile["personal"]["avatar_url"] = avatar_url
    elif existing_profile and existing_profile.get("personal", {}).get("avatar_url"):
        final_profile["personal"]["avatar_url"] = existing_profile["personal"]["avatar_url"]

    # Calculate completeness score based on filled sections
    completeness = 0
    pers = final_profile.get("personal", {})
    if pers.get("location") and pers.get("location").strip():
        completeness += 15
    if pers.get("avatar_url") and pers.get("avatar_url").strip():
        completeness += 5 # profile picture adds 5% completeness!
    
    edu = final_profile.get("education", [])
    if edu and any(e.get("school", "").strip() for e in edu):
        completeness += 20
        
    exp = final_profile.get("experience", [])
    if exp and any(ex.get("role", "").strip() for ex in exp):
        completeness += 20
        
    skills = final_profile.get("skills", [])
    if skills and any(s.strip() for s in skills if s):
        completeness += 15
        
    proj = final_profile.get("projects", [])
    if proj and any(p.get("title", "").strip() for p in proj):
        completeness += 15
        
    certs = final_profile.get("certificates", [])
    if certs and any(c.strip() for c in certs if c):
        completeness += 10 # adjusted to fit 100% total (15+5+20+20+15+15+10 = 100)

    final_profile["completeness"] = min(100, completeness)

    # Compute job compatibility scores for all available jobs
    compatibilities = []
    for job in JOBS:
        matched, missing, score = compute_skill_gap(final_profile.get("skills", []), job["required_skills"])
        compatibilities.append({
            "job_id": job["id"],
            "title": job["title"],
            "company": job["company"],
            "score": score,
            "matched_skills": matched,
            "missing_skills": missing
        })
    # Sort compatibilities by score descending
    compatibilities.sort(key=lambda x: x["score"], reverse=True)
    final_profile["job_compatibilities"] = compatibilities

    save_profile(final_profile)

    return redirect(url_for("build_profile_page"))
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
    try:
        return call_gemma(system, json.dumps(profile)).strip()
    except Exception as e:
        print(f"Error in generate_summary: {e}")
        skills = ", ".join(profile.get("skills", []))
        name = profile.get("personal", {}).get("name", "Candidate")
        role_part = f" for a {target} role" if target else ""
        return f"{name} is an experienced professional skilled in {skills or 'software development'}. Demonstrates a proven track record of successful projects, team collaboration, and technical execution, making them an excellent fit{role_part}."


def generate_about_me(profile):
    system = (
        "Write a warm, first-person 'About Me' paragraph (3-4 sentences) for a "
        "portfolio website, based on this profile. Professional but personable. "
        "Return ONLY the paragraph text, no labels, no markdown."
    )
    try:
        return call_gemma(system, json.dumps(profile)).strip()
    except Exception as e:
        print(f"Error in generate_about_me: {e}")
        name = profile.get("personal", {}).get("name", "I")
        skills = ", ".join(profile.get("skills", []))
        return f"Hi, I'm {name}! I am passionate about technology and solving complex problems. With skills in {skills or 'various areas'}, I love building impactful projects and learning new technologies. I am always excited to take on new challenges and collaborate with creative teams."


CREATED_CVS_FILE = "created_cvs.json"
TEMPLATES_LIST = [
    "dark_diagonal_sidebar",
    "warm_geometric_split",
    "arch_photo_two_tone",
    "navy_gold_sidebar",
    "sage_photo_block",
    "sage_photo_topbar",
    "dark_split_soft_shapes"
]

def load_created_cvs():
    if not os.path.exists(CREATED_CVS_FILE):
        return []
    with open(CREATED_CVS_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_created_cv(cv_record):
    cvs = load_created_cvs()
    cvs = [c for c in cvs if c["id"] != cv_record["id"]]
    cvs.append(cv_record)
    with open(CREATED_CVS_FILE, "w") as f:
        json.dump(cvs, f, indent=2)

def generate_cv_data_fallback(profile, job_title, company, template_id, schema):
    import copy
    fields = copy.deepcopy(schema)
    personal = profile.get("personal", {})
    
    if "name" in fields:
        fields["name"] = personal.get("name", "")
    if "title" in fields:
        fields["title"] = job_title
    if "photo_url" in fields:
        fields["photo_url"] = personal.get("photo_url", "https://i.pravatar.cc/150?img=33")
    
    summary_text = f"Highly motivated professional skilled in {', '.join(profile.get('skills', []))}. Eager to leverage my background to excel as a {job_title} at {company}."
    if "profile_summary" in fields:
        fields["profile_summary"] = summary_text
    if "profile_info" in fields:
        fields["profile_info"] = summary_text
        
    if "contact" in fields:
        contact_schema = fields["contact"]
        contact_data = {}
        contact_data["phone"] = personal.get("phone", "+8801700000000")
        contact_data["email"] = personal.get("email", "")
        contact_data["address"] = personal.get("location", "")
        if "website" in contact_schema or "website" in fields["contact"]:
            contact_data["website"] = "linkedin.com/in/" + personal.get("name", "candidate").lower().replace(" ", "")
        fields["contact"] = contact_data
        
    if "skills" in fields:
        skills_type = type(fields["skills"])
        profile_skills = profile.get("skills", [])
        if not profile_skills:
            profile_skills = ["Python", "Flask", "SQL"]
            
        if skills_type is list:
            if len(fields["skills"]) > 0 and isinstance(fields["skills"][0], dict):
                skill_item_template = fields["skills"][0]
                skills_list = []
                for s in profile_skills:
                    item = {}
                    if "name" in skill_item_template:
                        item["name"] = s
                    if "level_percent" in skill_item_template:
                        item["level_percent"] = 85
                    if "stars_out_of_5" in skill_item_template:
                        item["stars_out_of_5"] = 4
                    skills_list.append(item)
                fields["skills"] = skills_list
            else:
                fields["skills"] = profile_skills
                
    if "education" in fields:
        edu_list = []
        profile_edu = profile.get("education", [])
        if not profile_edu:
            profile_edu = [{"school": "University of Dhaka", "degree": "B.Sc. in Computer Science", "year": "2024"}]
        for e in profile_edu:
            item = {}
            item["school"] = e.get("school", "")
            item["degree"] = e.get("degree", "")
            item["years"] = e.get("year", "")
            if len(fields["education"]) > 0 and "bullets" in fields["education"][0]:
                item["bullets"] = [f"Graduated with honors in {e.get('year', '')}"]
            edu_list.append(item)
        fields["education"] = edu_list
        
    if "experience" in fields:
        exp_list = []
        profile_exp = profile.get("experience", [])
        if not profile_exp:
            profile_exp = [{"role": "Software Developer Intern", "company": "Tech Corp", "duration": "2023 - 2024", "description": "Developed backend APIs and optimized database queries."}]
        for ex in profile_exp:
            item = {}
            item["company"] = ex.get("company", "")
            item["role"] = ex.get("role", "")
            item["years"] = ex.get("duration", "")
            item["description"] = ex.get("description", "")
            if len(fields["experience"]) > 0 and "bullets" in fields["experience"][0]:
                item["bullets"] = [ex.get("description", "")]
            exp_list.append(item)
        fields["experience"] = exp_list
        
    if "references" in fields:
        fields["references"] = [{"name": "Dr. Rahman", "company_role": "Professor at CSE, DU", "phone": "+88015XXXXXXXX"}]
    if "languages" in fields:
        if len(fields["languages"]) > 0 and isinstance(fields["languages"][0], dict):
            fields["languages"] = [{"name": "English", "level_percent": 90}, {"name": "Bangla", "level_percent": 100}]
        else:
            fields["languages"] = ["English", "Bangla"]
    if "achievements" in fields:
        fields["achievements"] = [{"years": "2024", "description": "Winner of Local Tech Hackathon"}]
        
    return fields


def generate_cv_data(profile, job_title, company, job_description, template_id):
    schema = {}
    templates_path = os.path.join("readygrad_phase1_starter", "templates", "cv_templates.json")
    if not os.path.exists(templates_path):
        templates_path = os.path.join("templates", "cv_templates.json")
        
    with open(templates_path) as f:
        templates_data = json.load(f)
        for t in templates_data["templates"]:
            if t["template_id"] == template_id:
                schema = t["fields"]
                break
                
    system = (
        f"You are an expert CV writer. Given a candidate's profile and a target job, "
        f"populate the fields for the CV template style '{template_id}'. "
        f"Optimize and rewrite the profile summary, skills, experience bullet points, "
        f"and education to be highly professional and tailored specifically to match the target job "
        f"({job_title} at {company}). "
        f"Return ONLY valid JSON matching this exact structure, with no extra text or markdown code blocks:\n"
        f"{json.dumps(schema)}\n"
        f"Use the candidate's actual info (name, education, experience, skills, location, phone, email) "
        f"from their profile. If they have a profile photo/avatar, populate the photo_url field if it exists."
    )
    
    candidate_data = {
        "profile": profile,
        "job": {
            "title": job_title,
            "company": company,
            "description": job_description
        }
    }
    
    try:
        text = call_gemma(system, json.dumps(candidate_data))
        return clean_json(text)
    except Exception as e:
        print(f"Error in generate_cv_data using Gemini API: {e}")
        return generate_cv_data_fallback(profile, job_title, company, template_id, schema)

@app.route("/resume")
def resume():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    profile = get_user_profile(user["email"])
    if not profile:
        return redirect(url_for("build_profile_page"))
        
    cvs = load_created_cvs()
    user_cvs = [c for c in cvs if c.get("user_email") == user["email"]]
    
    error = request.args.get("error", "")
    success = request.args.get("success", "")
    
    return render_template("resume.html", profile=profile, cvs=user_cvs, user=user, error=error, success=success)

@app.route("/resume/create-custom", methods=["POST"])
def create_custom_cv():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    profile = get_user_profile(user["email"])
    if not profile:
        return redirect(url_for("build_profile_page"))
        
    job_title = request.form.get("job_title", "").strip()
    company = request.form.get("company", "").strip()
    job_description = request.form.get("job_description", "").strip()
    template_id = request.form.get("template_id", "").strip()
    
    if not job_title or not company:
        return redirect(url_for("resume", error="Job Title and Company Name are required."))
        
    # Check sufficiency
    missing_sections = []
    if not profile.get("education") or len(profile["education"]) == 0:
        missing_sections.append("Education")
    if not profile.get("experience") or len(profile["experience"]) == 0:
        missing_sections.append("Experience")
    if not profile.get("skills") or len(profile["skills"]) == 0:
        missing_sections.append("Skills")
        
    if missing_sections:
        error_msg = f"Your profile is missing: {', '.join(missing_sections)}. Please complete your profile first."
        return redirect(url_for("resume", error=error_msg))
        
    if not template_id or template_id == "random":
        template_id = random.choice(TEMPLATES_LIST)
        
    try:
        populated_data = generate_cv_data(profile, job_title, company, job_description, template_id)
        
        cv_record = {
            "id": f"cv_{int(datetime.now().timestamp())}",
            "user_email": user["email"],
            "job_id": None,
            "job_title": job_title,
            "company": company,
            "template_id": template_id,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "cv_data": populated_data
        }
        save_created_cv(cv_record)
        return redirect(url_for("resume", success="Custom CV generated successfully!"))
    except Exception as e:
        print("Error generating custom CV:", e)
        return redirect(url_for("resume", error="Failed to generate CV. Please try again."))

@app.route("/resume/view/<cv_id>")
def view_cv(cv_id):
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    cvs = load_created_cvs()
    cv = next((c for c in cvs if c["id"] == cv_id), None)
    if not cv:
        return "CV not found", 404
        
    profile = get_user_profile(user["email"])
    return render_template("cv_viewer.html", cv=cv, user=user, profile=profile)

@app.route("/resume/save-customized/<cv_id>", methods=["POST"])
def save_customized_cv(cv_id):
    user = session.get("user")
    if not user:
        return {"success": False, "error": "Unauthorized"}, 401
        
    cvs = load_created_cvs()
    cv_index = next((i for i, c in enumerate(cvs) if c["id"] == cv_id), -1)
    if cv_index == -1:
        return {"success": False, "error": "CV not found"}, 404
        
    if cvs[cv_index]["user_email"].strip().lower() != user["email"].strip().lower():
        return {"success": False, "error": "Unauthorized"}, 403
        
    data = request.json
    if not data or "cv_data" not in data:
        return {"success": False, "error": "Invalid data"}, 400
        
    cvs[cv_index]["cv_data"] = data.get("cv_data")
    cvs[cv_index]["custom_colors"] = data.get("custom_colors")
    
    with open(CREATED_CVS_FILE, "w") as f:
        json.dump(cvs, f, indent=2)
        
    return {"success": True}

@app.route("/resume/delete/<cv_id>")
def delete_cv(cv_id):
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    cvs = load_created_cvs()
    # Find CV to check if it's associated with a job
    cv_to_delete = next((c for c in cvs if c["id"] == cv_id), None)
    
    cvs = [c for c in cvs if c["id"] != cv_id]
    with open(CREATED_CVS_FILE, "w") as f:
        json.dump(cvs, f, indent=2)
        
    # If the CV has an associated job_id, delete that application too
    if cv_to_delete and cv_to_delete.get("job_id"):
        job_id = int(cv_to_delete.get("job_id"))
        apps = load_applications()
        apps = [a for a in apps if a["job_id"] != job_id]
        with open(APPLICATIONS_FILE, "w") as f:
            json.dump(apps, f, indent=2)
            
    return redirect(url_for("resume"))


@app.route("/portfolio")
def portfolio():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    profile = get_user_profile(user["email"])
    if not profile:
        return redirect(url_for("build_profile_page"))
        
    about_me = generate_about_me(profile)
    return render_template("portfolio.html", profile=profile, about_me=about_me, user=user)


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


def load_saved_job_ids(email=None):
    if not os.path.exists(SAVED_JOBS_FILE):
        return []
    with open(SAVED_JOBS_FILE) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []
    if isinstance(data, dict):
        if email:
            return data.get(email.strip().lower(), [])
        all_ids = []
        for ids in data.values():
            if isinstance(ids, list):
                all_ids.extend(ids)
        return list(set(all_ids))
    elif isinstance(data, list):
        return data
    return []


def save_job_id(job_id, email=None):
    if not email:
        user = session.get("user")
        email = user["email"] if user else "default"
    email_key = email.strip().lower()

    data = {}
    if os.path.exists(SAVED_JOBS_FILE):
        with open(SAVED_JOBS_FILE) as f:
            try:
                raw_data = json.load(f)
                if isinstance(raw_data, dict):
                    data = raw_data
                elif isinstance(raw_data, list):
                    data[email_key] = raw_data
            except json.JSONDecodeError:
                data = {}
    if email_key not in data:
        data[email_key] = []
    if job_id not in data[email_key]:
        data[email_key].append(job_id)
    with open(SAVED_JOBS_FILE, "w") as f:
        json.dump(data, f, indent=2)

    db.save_job_id_db(job_id, email_key)


def delete_saved_job_id(job_id, email=None):
    if not email:
        user = session.get("user")
        email = user["email"] if user else "default"
    email_key = email.strip().lower()

    if os.path.exists(SAVED_JOBS_FILE):
        with open(SAVED_JOBS_FILE) as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
        if isinstance(data, dict) and email_key in data:
            if job_id in data[email_key]:
                data[email_key].remove(job_id)
            with open(SAVED_JOBS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        elif isinstance(data, list):
            if job_id in data:
                data.remove(job_id)
            with open(SAVED_JOBS_FILE, "w") as f:
                json.dump(data, f, indent=2)

    db.delete_saved_job_id_db(job_id, email_key)


def get_job_recommendations(profile, jobs):
    system = (
        "Given a candidate's skills and a list of jobs (id, title, company, "
        "required_skills), pick the 4 best-matching job ids for this candidate. "
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
        res = clean_json(text)
        if isinstance(res, list) and len(res) > 0:
            return res
    except Exception as e:
        print(f"Error in get_job_recommendations: {e}")

    # Fallback: calculate skill gap score for each job locally
    scored_jobs = []
    user_skills = profile.get("skills", [])
    for j in jobs:
        matched, missing, score = compute_skill_gap(user_skills, j["required_skills"])
        reason = f"Matches {len(matched)} of {len(j['required_skills'])} key skills ({', '.join(matched[:2]) if matched else 'Great entry opportunity'})."
        scored_jobs.append({
            "id": j["id"],
            "title": j["title"],
            "company": j["company"],
            "reason": reason,
            "_score": score
        })
    scored_jobs.sort(key=lambda x: x["_score"], reverse=True)
    return scored_jobs[:4]


@app.route("/jobs")
def browse_jobs():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    profile = get_user_profile(user["email"])
    
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

    saved_ids = load_saved_job_ids(user["email"])
    recommendations = get_job_recommendations(profile, JOBS) if profile else []
    applications = load_applications()
    applied_ids = [a["job_id"] for a in applications if a.get("user_email") == user["email"]]

    return render_template(
        "jobs.html",
        jobs=filtered,
        saved_ids=saved_ids,
        applied_ids=applied_ids,
        recommendations=recommendations,
        industries=sorted(set(j["industry"] for j in JOBS)),
        locations=sorted(set(j["location"] for j in JOBS)),
        experiences=sorted(set(j["experience"] for j in JOBS)),
        filters={"industry": industry, "location": location, "experience": experience, "remote": remote},
        user=user,
        profile=profile
    )


@app.route("/jobs/save/<int:job_id>")
def save_job(job_id):
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    save_job_id(job_id, user["email"])
    
    ref = request.args.get("from", "jobs")
    if ref == "detail":
        return redirect(url_for("job_detail", job_id=job_id))
    return redirect("/jobs")

@app.route("/jobs/unsave/<int:job_id>")
def unsave_job(job_id):
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    delete_saved_job_id(job_id, user["email"])
    
    ref = request.args.get("from", "jobs")
    if ref == "detail":
        return redirect(url_for("job_detail", job_id=job_id))
    elif ref == "saved":
        return redirect("/jobs/saved")
    return redirect("/jobs")


@app.route("/jobs/saved")
def saved_jobs():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    saved_ids = load_saved_job_ids(user["email"])
    jobs = [j for j in JOBS if j["id"] in saved_ids]
    applications = load_applications()
    applied_ids = [a["job_id"] for a in applications if a.get("user_email") == user["email"]]
    return render_template("saved_jobs.html", jobs=jobs, applied_ids=applied_ids, user=user)


APPLICATIONS_FILE = "applications.json"


def compute_skill_gap(profile_skills, job_skills):
    profile_lower = [s.strip().lower() for s in profile_skills]
    matched = [s for s in job_skills if s.strip().lower() in profile_lower]
    missing = [s for s in job_skills if s.strip().lower() not in profile_lower]
    score = round(len(matched) / len(job_skills) * 100) if job_skills else 100
    return matched, missing, score


def generate_readiness_narrative(job, matched, missing, score):
    system = (
        "In 2-3 sentences, explain this readiness score to the candidate in plain, "
        "encouraging language: what they already have going for them, and what's missing. "
        "Return ONLY the explanation text, no markdown."
    )
    content = json.dumps({"job_title": job["title"], "score": score, "matched_skills": matched, "missing_skills": missing})
    try:
        return call_gemma(system, content).strip()
    except Exception as e:
        print(f"Error in generate_readiness_narrative: {e}")
        matched_str = ", ".join(matched) if matched else "none"
        missing_str = ", ".join(missing) if missing else "none"
        return f"Based on our analysis, your profile matches some required skills for the {job['title']} role, including: {matched_str}. To raise your score of {score}%, we suggest highlighting or gaining experience in missing skills: {missing_str}. You are on the right track!"


def generate_cover_letter(profile, job):
    system = (
        "Write a professional, concise cover letter (3-4 paragraphs) for this candidate "
        "applying to this specific job. Reference relevant skills and projects from their "
        "profile that match the job's required skills. Do not invent experience not in the "
        "profile. Return ONLY the cover letter text, no labels, no markdown."
    )
    content = json.dumps({"profile": profile, "job": job})
    try:
        return call_gemma(system, content).strip()
    except Exception as e:
        print(f"Error in generate_cover_letter: {e}")
        personal = profile.get("personal", {})
        name = personal.get("name", "Applicant")
        email = personal.get("email", "")
        location = personal.get("location", "")
        skills = ", ".join(profile.get("skills", []))
        return f"""Dear Hiring Team at {job['company']},

I am writing to express my strong interest in the {job['title']} position. With my background and skills in {skills or 'software development'}, I am confident in my ability to contribute effectively to your team.

Throughout my career and academic projects, I have demonstrated a strong commitment to quality and teamwork. I am excited about the opportunity to bring my skills to your organization.

Thank you for your time and consideration.

Sincerely,
{name}
{email}
{location}"""


def generate_application_email(profile, job):
    system = (
        "Write a short, professional application email (4-6 sentences) that the candidate "
        "could send to accompany their application. Mention the specific role and company. "
        "Return ONLY the email text including a greeting and sign-off, no subject line, no markdown."
    )
    content = json.dumps({"profile": profile, "job": job})
    try:
        return call_gemma(system, content).strip()
    except Exception as e:
        print(f"Error in generate_application_email: {e}")
        personal = profile.get("personal", {})
        name = personal.get("name", "Applicant")
        return f"Dear Hiring Manager,\n\nPlease find attached my CV and application for the {job['title']} position at {job['company']}. With my experience and skills, I am excited about the prospect of contributing to your team.\n\nThank you for considering my application.\n\nBest regards,\n{name}"


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
    apps = [a for a in apps if a["job_id"] != app_record["job_id"] or a.get("user_email") != app_record.get("user_email")]
    apps.append(app_record)
    with open(APPLICATIONS_FILE, "w") as f:
        json.dump(apps, f, indent=2)
    try:
        db.save_application_db(app_record)
    except Exception as e:
        print(f"Database sync warning in save_application: {e}")


@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    profile = get_user_profile(user["email"])
    if not profile:
        return redirect(url_for("build_profile_page"))

    job = next((j for j in JOBS if j["id"] == job_id), None)
    if not job:
        return "Job not found", 404

    matched, missing, score = compute_skill_gap(profile.get("skills", []), job["required_skills"])
    narrative = generate_readiness_narrative(job, matched, missing, score)
    applications = load_applications()
    already_applied = any(a["job_id"] == job_id and (a.get("user_email") == user["email"] or a.get("user_email") is None) for a in applications)
    saved_ids = load_saved_job_ids(user["email"])

    return render_template(
        "job_detail.html", job=job, score=score, matched=matched, missing=missing,
        narrative=narrative, already_applied=already_applied, user=user, profile=profile,
        saved_ids=saved_ids
    )


@app.route("/jobs/<int:job_id>/apply")
def apply_to_job(job_id):
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    profile = get_user_profile(user["email"])
    if not profile:
        return redirect(url_for("build_profile_page"))

    job = next((j for j in JOBS if j["id"] == job_id), None)
    if not job:
        return "Job not found", 404

    # Sufficiency Check
    missing_sections = []
    if not profile.get("education") or len(profile["education"]) == 0:
        missing_sections.append("Education")
    if not profile.get("experience") or len(profile["experience"]) == 0:
        missing_sections.append("Experience")
    if not profile.get("skills") or len(profile["skills"]) == 0:
        missing_sections.append("Skills")
        
    if missing_sections:
        warning_msg = f"Your profile is missing: {', '.join(missing_sections)}. Please fill up your profile info to generate your CV."
        matched, missing, score = compute_skill_gap(profile.get("skills", []), job["required_skills"])
        narrative = generate_readiness_narrative(job, matched, missing, score)
        applications = load_applications()
        already_applied = any(a["job_id"] == job_id for a in applications)
        return render_template(
            "job_detail.html", job=job, score=score, matched=matched, missing=missing,
            narrative=narrative, already_applied=already_applied, user=user, profile=profile,
            warning=warning_msg
        )

    # Create CV
    template_id = random.choice(TEMPLATES_LIST)
    try:
        populated_data = generate_cv_data(profile, job["title"], job["company"], job["description"], template_id)
        cv_id = f"cv_{int(datetime.now().timestamp())}"
        cv_record = {
            "id": cv_id,
            "user_email": user["email"],
            "job_id": job_id,
            "job_title": job["title"],
            "company": job["company"],
            "template_id": template_id,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "cv_data": populated_data
        }
        save_created_cv(cv_record)
        
        session[f"pending_cv_{job_id}"] = cv_record
        session.modified = True
        
        return redirect(url_for("apply_step2", job_id=job_id))
    except Exception as e:
        print("Error generating CV for application:", e)
        return "Failed to generate CV. Please try again.", 500

@app.route("/jobs/<int:job_id>/save-temp-application", methods=["POST"])
def save_temp_application(job_id):
    user = session.get("user")
    if not user:
        return {"success": False, "error": "Unauthorized"}, 401
    data = request.get_json() or {}
    session[f"temp_email_{job_id}"] = data.get("email")
    session[f"temp_cover_letter_{job_id}"] = data.get("cover_letter")
    session.modified = True
    return {"success": True}


@app.route("/jobs/<int:job_id>/apply-step2")
def apply_step2(job_id):
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    profile = get_user_profile(user["email"])
    if not profile:
        return redirect(url_for("build_profile_page"))

    job = next((j for j in JOBS if j["id"] == job_id), None)
    if not job:
        return "Job not found", 404
        
    pending_cv = session.get(f"pending_cv_{job_id}")
    if not pending_cv:
        return redirect(url_for("apply_to_job", job_id=job_id))
        
    # Check for temporary saved edits in session
    cover_letter = session.get(f"temp_cover_letter_{job_id}")
    if not cover_letter:
        cover_letter = generate_cover_letter(profile, job)
        
    email = session.get(f"temp_email_{job_id}")
    if not email:
        email = generate_application_email(profile, job)
    
    return render_template(
        "apply_step2.html",
        job=job,
        cv=pending_cv,
        cover_letter=cover_letter,
        email=email,
        user=user,
        profile=profile
    )

@app.route("/jobs/<int:job_id>/apply-submit", methods=["POST"])
def apply_submit(job_id):
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    profile = get_user_profile(user["email"])
    if not profile:
        return redirect(url_for("build_profile_page"))

    job = next((j for j in JOBS if j["id"] == job_id), None)
    if not job:
        return "Job not found", 404
        
    email_content = request.form.get("email", "")
    cover_letter = request.form.get("cover_letter", "")
    
    matched, missing, score = compute_skill_gap(profile.get("skills", []), job["required_skills"])
    
    app_record = {
        "job_id": job_id,
        "job_title": job["title"],
        "company": job["company"],
        "status": "Applied",
        "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "readiness_score": score,
        "cover_letter": cover_letter,
        "email": email_content,
        "user_email": user["email"]
    }
    save_application(app_record)
    
    session.pop(f"pending_cv_{job_id}", None)
    session.pop(f"temp_email_{job_id}", None)
    session.pop(f"temp_cover_letter_{job_id}", None)
    session.modified = True
    
    return redirect(url_for("apply_success", job_id=job_id))


@app.route("/jobs/apply-success/<int:job_id>")
def apply_success(job_id):
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    job = next((j for j in JOBS if j["id"] == job_id), None)
    if not job:
        return "Job not found", 404
    return render_template("apply_success.html", job=job, user=user)


@app.route("/applications")
def applications_list():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    profile = get_user_profile(user["email"])
    
    apps = load_applications()
    user_apps = [a for a in apps if a.get("user_email") == user["email"] or a.get("user_email") is None]
    return render_template("applications.html", applications=user_apps, user=user, profile=profile)


@app.route("/applications/<int:job_id>")
def application_detail(job_id):
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    profile = get_user_profile(user["email"])
    
    apps = load_applications()
    user_apps = [a for a in apps if a.get("user_email") == user["email"] or a.get("user_email") is None]
    application = next((a for a in user_apps if a["job_id"] == job_id), None)
    if not application:
        return "No application found for this job yet.", 404
        
    cvs = load_created_cvs()
    cv = next((c for c in cvs if c.get("job_id") == job_id and c.get("user_email") == user["email"]), None)
    
    return render_template("application_detail.html", application=application, user=user, profile=profile, cv=cv)


@app.route("/update-application-status", methods=["POST"])
def update_application_status():
    user = session.get("user")
    if not user:
        return {"success": False, "error": "Unauthorized"}, 401
        
    data = request.json
    if data.get("action") == "clear":
        session["notifications"] = []
        session.modified = True
        return {"success": True}
        
    job_id = data.get("job_id")
    new_status = data.get("status")
    
    if not job_id or not new_status:
        return {"success": False, "error": "Missing parameters"}, 400
        
    apps = load_applications()
    app_record = None
    for a in apps:
        if a["job_id"] == int(job_id):
            a["status"] = new_status
            app_record = a
            break
            
    if not app_record:
        return {"success": False, "error": "Application not found"}, 404
        
    with open(APPLICATIONS_FILE, "w") as f:
        json.dump(apps, f, indent=2)
        
    # Generate custom notification message
    notif_msg = f"Application for {app_record['job_title']} at {app_record['company']} updated to: {new_status}"
    if new_status == "Accepted":
        notif_msg = f"🎉 Congratulations! Your application for {app_record['job_title']} at {app_record['company']} has been ACCEPTED!"
    elif new_status == "Denied":
        notif_msg = f"Your application for {app_record['job_title']} at {app_record['company']} has been Denied."
    elif new_status == "In Process":
        notif_msg = f"Your application for {app_record['job_title']} at {app_record['company']} is now In Process."
        
    if "notifications" not in session:
        session["notifications"] = []
        
    notif = {
        "id": datetime.now().timestamp(),
        "message": notif_msg,
        "type": new_status,
        "time": datetime.now().strftime("%I:%M %p"),
        "unread": True
    }
    
    session["notifications"].insert(0, notif)
    session.modified = True
    
    return {"success": True, "notification": notif}


if __name__ == "__main__":
    app.run(debug=True, port=5000)

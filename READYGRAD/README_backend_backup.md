# ReadyGrad — Phase 1 Starter (Python + Flask + Gemma 4)

This is a working starting point for Phase 1. Follow these steps in order.

## Step 0 — Things to install (do this first, only once)

1. **Python** — if you don't have it, download from python.org (3.10 or newer).
2. **VS Code** (or any code editor) — download from code.visualstudio.com. This is where you'll open and edit these files.
3. A **terminal** — VS Code has one built in (menu: Terminal → New Terminal).

## Step 1 — Where to put this folder

Move this whole `readygrad_phase1_starter` folder anywhere easy to find, like your Desktop.
Then in VS Code: **File → Open Folder** → select `readygrad_phase1_starter`.
Everything you need is inside it — you don't need to create any files yourself, they're already here.

## Step 2 — Get your Gemma 4 API key (free)

1. Go to **aistudio.google.com/apikey** in your browser.
2. Sign in with a Google account.
3. Click **Create API key**. Copy it.
4. In VS Code, rename the file `.env.example` to `.env` (just remove `.example`).
5. Open `.env` and paste your key so it looks like:
   ```
   GEMINI_API_KEY=AIzaSy...your_actual_key...
   ```
6. Save the file.

## Step 3 — Install the Python packages

In the VS Code terminal, type these one at a time and press Enter after each:

```
python -m venv venv
```
Then, on Mac/Linux:
```
source venv/bin/activate
```
Or on Windows:
```
venv\Scripts\activate
```
Then:
```
pip install -r requirements.txt
```
This installs Flask (the web server), python-dotenv (reads your API key), and google-genai (talks to Gemma 4).

## Step 4 — Run it

In the terminal:
```
python app.py
```
You'll see a message like `Running on http://127.0.0.1:5000`. Open that address in your browser.

## What each sub-phase looks like in this project

**1.1 — Schema.** You don't write this yourself — look inside `app.py` at the `organize_profile` function. The JSON shape written there IS your schema.

**1.2 — Raw input UI.** This is `templates/profile_form.html`. It's one simple page with plain text boxes — people type naturally, they don't need to format anything.

**1.3 — Gemma 4 organize pass.** This is the `organize_profile()` function in `app.py`. It sends the messy form text to Gemma 4 and gets back clean, structured JSON.

**1.4 — Gemma 4 rewrite pass.** This is the `rewrite_profile()` function in `app.py`. It takes the clean JSON and rewrites the description fields into proper resume-style bullet points.

**1.5 — Save as master record.** This is the `save_profile()` function. It stores everything in a file called `profiles.json`, which gets created automatically the first time someone submits the form — you'll see it appear in your folder after your first test. **This file is where all your data lives** — no separate database needed for a one-day build.

## Testing it

1. Fill out the form with some real-sounding info (even fake test data is fine).
2. Click "Generate My Profile with Gemma 4".
3. You should see the organized, rewritten JSON on the next page.
4. Check your folder — a new `profiles.json` file should now exist with that data saved inside it.

## If something breaks

- **"No module named flask"** → you forgot Step 3, or forgot to activate the venv before running `python app.py`.
- **API key error** → double check `.env` has no extra spaces and the key was copied fully.
- **JSON parsing error on Gemma's response** → open a terminal print of `text` before `clean_json()` runs, to see exactly what Gemma sent back; occasionally you may need to re-run.

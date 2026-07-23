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
import database as db
db.init_db()
MODEL = "gemma-4-26b-a4b-it"

if __name__ == "__main__":
    app.run(debug=True, port=5000)

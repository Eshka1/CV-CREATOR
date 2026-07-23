import json
import database as db

db.init_db()

 
with open("profiles.json") as f:
    profiles = json.load(f)
for p in profiles:
    db.save_profile_db(p)

 
with open("applications.json") as f:
    apps = json.load(f)
for a in apps:
    db.save_application_db(a)

print("Migration complete.")
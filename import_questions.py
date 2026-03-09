import json
from supabase import create_client

SUPABASE_URL = "https://xxxxxx.supabase.co"
SUPABASE_KEY = "xxxxxx"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

with open("questions.json", encoding="utf-8") as f:
    questions = json.load(f)

# Upsert pour éviter les doublons
res = supabase.table("questions").upsert(questions).execute()
print(f"✅ {len(res.data)} questions importées")
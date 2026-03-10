import json
from supabase import create_client

SUPABASE_URL = "https://qsmryrxztauatobrtbww.supabase.co"
SUPABASE_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

with open("questions.json", encoding="utf-8") as f:
    questions = json.load(f)

# Upsert pour éviter les doublons
res = supabase.table("questions").upsert(questions).execute()
print(f"✅ {len(res.data)} questions importées")
import json
from supabase import create_client

SUPABASE_URL = "https://qsmryrxztauatobrtbww.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFzbXJ5cnh6dGF1YXRvYnJ0Ynd3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNjM3OTgsImV4cCI6MjA4ODYzOTc5OH0.ng_hCNpiy8t_9NjTHm_zj4JzjxsjMnX5AKg5EBmoB1I"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

with open("questions.json", encoding="utf-8") as f:
    questions = json.load(f)

# Upsert pour éviter les doublons
res = supabase.table("questions").upsert(questions).execute()
print(f"✅ {len(res.data)} questions importées")
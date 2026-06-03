"""Test with gemini-2.0-flash-lite"""
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv()
import os
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
models = ["gemini-2.0-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"]
for model in models:
    try:
        print(f"Trying {model}...")
        r = client.models.generate_content(model=model, contents="Say hello in 2 words")
        print(f"SUCCESS: {r.text.strip()}")
        print(f"\nUSE MODEL: {model}")
        break
    except Exception as e:
        err = str(e)[:300]
        print(f"FAIL: {err}\n")

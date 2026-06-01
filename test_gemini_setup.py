import os
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("dotenv loaded successfully")
except ImportError:
    print("dotenv not installed")

print("API Key exists:", bool(os.environ.get("GEMINI_API_KEY")))
try:
    import google.generativeai as genai
    print("google.generativeai imported successfully")
except ImportError as e:
    print("google.generativeai import failed:", e)

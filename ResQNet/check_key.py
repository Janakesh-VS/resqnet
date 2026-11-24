from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")

if api_key:
    print("Gemini API key configured successfully!")
else:
    print("API key not found!")
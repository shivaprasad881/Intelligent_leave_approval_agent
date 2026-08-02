import os
import sys
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("GOOGLE_API_KEY")
print(f"GOOGLE_API_KEY present: {bool(key)}")

print("\n--- 1. Testing official google.genai SDK ---")
try:
    from google import genai
    client = genai.Client(api_key=key)
    print("Testing generate_content with gemini-2.5-flash...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Hello! Reply in 3 words."
    )
    print("SUCCESS (google.genai):", response.text)
except Exception as e:
    print(f"ERROR (google.genai): {type(e).__name__}: {e}")

print("\n--- 2. Testing langchain_google_genai ---")
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=key, transport="rest")
    res = llm.invoke("Hello, answer in 3 words.")
    print("SUCCESS (langchain_google_genai):", res.content)
except Exception as e:
    print(f"ERROR (langchain_google_genai): {type(e).__name__}: {e}")

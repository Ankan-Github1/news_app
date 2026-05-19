# from google import genai
# from dotenv import load_dotenv
# from openai import OpenAI
# load_dotenv()
# import os

# client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# def summarise_test(goal, article):
#     response = client.models.generate_content(
#     model="gemini-2.0-flash",
#     contents=f"This is a news article: {article}\n\nSummarise the article in the context of this goal: {goal}",
#     )

#     return response.text

import requests

SUMMARISE_MODEL_NAME = "llama3.1:8b"  # replace with your actual model name or endpoint

def summarise_test(goal_text, article):
    system = "You analyze news articles for a specific reader. Be concrete and direct. No filler phrases like 'this article discusses'."
    prompt = f"""Reader's goal:
{goal_text}

Article:
{article}

Write exactly three short sections:
1. What happened (2-3 sentences, just facts)
2. Why it matters for this reader — be specific. If it barely matters, say so honestly.
3. One concrete takeaway.
"""
    res = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": SUMMARISE_MODEL_NAME,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_ctx": 8192}
        }
    )
    return res.json()["response"]


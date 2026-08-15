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
from src.storage.db import get_summary, insert_summary

SUMMARISE_MODEL_NAME = "llama3.1:8b"  # replace with your actual model name or endpoint

def summarise_text(goal_text, article):
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
    try:
        res = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": SUMMARISE_MODEL_NAME,
                "system": system,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_ctx": 8192
                }
            },
            timeout=120
        )

        res.raise_for_status()

        return res.json()["response"]

    except (requests.RequestException, KeyError, ValueError):
        return None


def get_or_compute_summary(article_id, goal_id, model_name, goal_text, article_text):
    """
    Retrieve the summary from the database if it exists; otherwise, compute it using the LLM.
    """
    summary = get_summary(article_id, goal_id, model_name)
    if summary is not None:
        return summary
    else:
        # If no summary exists, compute it using the LLM
        computed_summary = summarise_text(goal_text, article_text)
        if computed_summary is not None:
            insert_summary(article_id, goal_id, model_name, computed_summary)
        return computed_summary
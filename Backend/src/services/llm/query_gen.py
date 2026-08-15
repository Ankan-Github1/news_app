import requests
import json

QUERY_MODEL_NAME = "llama3.1:8b"

SYSTEM = (
    "You turn a person's goal into search keywords for a news API. "
    "The API does plain keyword matching, not semantic search: short common "
    "noun phrases find articles, long descriptive sentences find nothing. "
    "Respond with JSON only."
)


def extract_queries(goal_text, attempts=3):
    prompt = f"""Goal: {goal_text}

    Give 1-3 search queries that would find news articles relevant to this goal.

    Rules:
    - Each query is 1-3 words. A topic name, not a sentence.
    - Use words a journalist would actually print.
    - Drop the personal parts (names, places, feelings). Keep the subject.

    Examples:

    Goal: be good table tennis player and impress aunties in the TT court in apartment
    {{"queries": ["table tennis", "table tennis tournament"]}}

    Goal: get a job as a backend developer at a startup
    {{"queries": ["software hiring", "startup jobs", "backend development"]}}

    Now do the same for the goal above. Respond with exactly this shape:
    {{"queries": ["...", "..."]}}"""

    for attempt in range(1, attempts + 1):
        try:
            res = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": QUERY_MODEL_NAME,
                    "system": SYSTEM,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.3, "num_ctx": 2048},
                },
                timeout=60
            )
            res.raise_for_status()
            body = res.json()
        except (requests.RequestException, ValueError) as e:
            print(f"[query_gen] attempt {attempt}: request failed: {e}")
            continue

        raw = body.get("response")
        if raw is None:
            print(f"[query_gen] attempt {attempt}: no 'response' field, got {body}")
            continue

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[query_gen] attempt {attempt}: not valid JSON: {raw!r}")
            continue

        # the model may wrap the list in a dict under a key of its own choosing
        if isinstance(data, dict):
            lists = [v for v in data.values() if isinstance(v, list)]
            data = lists[0] if lists else None

        if not isinstance(data, list):
            print(f"[query_gen] attempt {attempt}: wanted a list, got {type(data).__name__}: {raw!r}")
            continue

        queries = [q.strip() for q in data if isinstance(q, str) and q.strip()]
        if not queries:
            print(f"[query_gen] attempt {attempt}: no usable strings in {raw!r}")
            continue

        return queries

    # every attempt failed: the goal itself is probably the problem, not the model
    print(f"[query_gen] all {attempts} attempts failed for goal {goal_text!r}, using fallback")
    words = sorted((w.strip(".,!?") for w in goal_text.split()), key=len, reverse=True)
    return [w for w in words if len(w) > 3][:3] or [goal_text]
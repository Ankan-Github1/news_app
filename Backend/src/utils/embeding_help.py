import hashlib


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def goal_to_text(goal):
    return f"""
    Goal: {goal['name']}

    Description: {goal['description']}

    Focus Areas: {", ".join(goal['focus_areas'])}

    Signals of Interest: {", ".join(goal['signal_for_interest'])}
    """
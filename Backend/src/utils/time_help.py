import time
from datetime import datetime, timedelta

def get_date():
    return {"Date": time.strftime("%Y-%m-%d"),
            "Previous Date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            }

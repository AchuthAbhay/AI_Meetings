import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)        # ye apna summary module hai snar pro api key use kiya hai 

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

class SummarizerModule:
    def __init__(self):
        if not PERPLEXITY_API_KEY:
            raise ValueError("PERPLEXITY_API_KEY not found in .env")

    def summarize(self, transcript_text: str) -> str:
        """
        Generate a structured professional meeting summary
        """

        prompt = f"""
You are an expert government meeting analyst.

From the transcript below, generate a PROFESSIONAL, STRUCTURED MEETING SUMMARY.

FORMAT STRICTLY AS:

EXECUTIVE SUMMARY:
- 3–5 bullet points describing what happened overall

KEY DECISIONS:
- Bullet list of decisions (include approvals/rejections)

ACTION ITEMS:
- Bullet list with owner + responsibility (if mentioned)

CONTROVERSIES / CONCERNS:
- Bullet list of disagreements or public concerns

IMPORTANT QUOTES:
- Short impactful quotes with speaker names

TRANSCRIPT:
\"\"\"
{transcript_text}
\"\"\"
"""

        payload = {
            "model": "sonar-pro",
            "messages": [
                {"role": "system", "content": "You summarize meetings accurately and professionally."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }

        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post(PERPLEXITY_URL, json=payload, headers=headers, timeout=120)

        if response.status_code != 200:
            logger.error(response.text)
            raise RuntimeError("Perplexity API failed")

        return response.json()["choices"][0]["message"]["content"]

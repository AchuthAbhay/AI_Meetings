import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"


class SummarizerModule:

    def __init__(self):

        if not PERPLEXITY_API_KEY:
            raise ValueError("PERPLEXITY_API_KEY not found in .env")

    def summarize(self, transcript_text: str) -> str:
        """
        Meeting transcript ko structured professional summary me convert karta hai.
        Supports speaker-labeled transcripts from AssemblyAI.
        """

        logger.info("Generating meeting summary using Sonar-Pro")

        prompt = f"""
You are an expert government meeting analyst.

Your task is to generate a PROFESSIONAL STRUCTURED MEETING SUMMARY.

The transcript contains multiple speakers labeled like:
[Speaker A], [Speaker B], etc.

Analyze carefully and produce this EXACT format:

EXECUTIVE SUMMARY:
- 3–5 bullet points explaining overall meeting outcome

KEY DECISIONS:
- Bullet list of approved/rejected items

CONTROVERSIES / CONCERNS:
- Bullet list of disagreements, concerns, objections

ACTION ITEMS:
- Bullet list of tasks assigned (who must do what)

IMPORTANT QUOTES:
- Include impactful quotes WITH speaker labels

MEETING SENTIMENT:
- Overall tone: Positive / Neutral / Negative
- Short explanation why

TRANSCRIPT:
\"\"\"
{transcript_text}
\"\"\"
"""

        payload = {

            "model": "sonar-pro",

            "messages": [
                {
                    "role": "system",
                    "content": "You are a precise meeting summarization assistant."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            "temperature": 0.2
        }

        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            PERPLEXITY_URL,
            json=payload,
            headers=headers,
            timeout=120
        )

        if response.status_code != 200:

            logger.error(response.text)

            raise RuntimeError("Perplexity API failed")

        summary = response.json()["choices"][0]["message"]["content"]

        logger.info("Summary generated successfully")

        return summary
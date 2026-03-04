import os
import logging
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


class SummarizerModule:
    """
    Meeting transcript ko structured professional summary me convert karta hai.
    Ab Perplexity Sonar-Pro ki jagah Groq LLaMA-3.1-8B use karta hai.
    """

    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not found in .env")

        # Groq client
        self.client = Groq(api_key=GROQ_API_KEY)
        # Fast + good quality model
        self.model = "llama-3.1-8b-instant"
        logger.info("SummarizerModule (Groq) initialized")

    def summarize(self, transcript_text: str) -> str:
        """
        Full transcript (speaker-labeled text) ko structured summary me convert karta hai.
        """

        if not transcript_text.strip():
            raise ValueError("Transcript text is empty")

        logger.info("Generating meeting summary using Groq LLaMA")

        prompt = f"""
You are an expert government and corporate meeting analyst.

Your task is to generate a PROFESSIONAL STRUCTURED MEETING SUMMARY.

The transcript contains multiple speakers labeled like:
Speaker 0, Speaker 1, etc.

Analyse carefully and produce this EXACT format:

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
{transcript_text[:12000]}
\"\"\"
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise meeting summarization assistant. "
                                   "Return only the summary in the requested format.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.2,
                max_tokens=1500,
            )

            summary = response.choices[0].message.content.strip()
            logger.info("Summary generated successfully (Groq)")
            return summary

        except Exception as e:
            logger.error(f"Groq summarization failed: {e}")
            raise RuntimeError("Groq API failed for summary")

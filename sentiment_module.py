import os
import json
import logging
from groq import Groq

logger = logging.getLogger(__name__)

SENTIMENT_PROMPT = """You are analyzing a government/council meeting transcript for sentiment.

For each distinct speaker or topic block, identify:
- The speaker label (if available) or a short topic label
- Overall sentiment: Positive, Negative, or Neutral
- Intensity score: 0.0 to 1.0 (how strongly positive or negative)
- A one-line reason explaining the sentiment

Then provide an overall meeting sentiment summary.

Return ONLY valid JSON in this exact format:
{
  "segments": [
    {
      "label": "Speaker_00 or topic label",
      "sentiment": "Positive|Negative|Neutral",
      "score": 0.0,
      "reason": "brief explanation"
    }
  ],
  "overall": {
    "sentiment": "Positive|Negative|Neutral",
    "score": 0.0,
    "summary": "2-3 sentence summary of the emotional tone of the meeting"
  }
}

Transcript:
"""


class SentimentModule:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in environment")
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"

    def analyze(self, transcript_text: str) -> dict:
        """
        Accepts plain transcript text or a pre-joined string of speaker segments.
        Returns a dict with 'segments' and 'overall' keys.
        """
        if not transcript_text or not transcript_text.strip():
            raise ValueError("Transcript text is empty")

        # Trim to avoid hitting token limits — Groq's llama3-70b has 8192 ctx
        trimmed = transcript_text[:12000]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise sentiment analysis assistant. Always return valid JSON only, no markdown, no explanation outside the JSON."
                    },
                    {
                        "role": "user",
                        "content": SENTIMENT_PROMPT + trimmed
                    }
                ],
                temperature=0.2,
                max_tokens=1500
            )

            raw = response.choices[0].message.content.strip()

            # Strip markdown code fences if model wraps anyway
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            result = json.loads(raw)
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Sentiment JSON parse error: {e}\nRaw: {raw}")
            raise ValueError(f"Failed to parse sentiment response: {e}")
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            raise

    def format_for_display(self, result: dict) -> str:
        """
        Returns a plain text summary for simple display fallback.
        """
        lines = []
        overall = result.get("overall", {})
        lines.append(f"Overall: {overall.get('sentiment', 'N/A')} (score: {overall.get('score', 0):.2f})")
        lines.append(overall.get("summary", ""))
        lines.append("")

        for seg in result.get("segments", []):
            lines.append(
                f"{seg['label']}: {seg['sentiment']} ({seg['score']:.2f}) — {seg['reason']}"
            )

        return "\n".join(lines)

    def save_to_file(self, result: dict, path: str = "transcripts/sentiment.json"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Sentiment saved to {path}")
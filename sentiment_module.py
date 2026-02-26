import os
import json
import logging
from groq import Groq
from dotenv import load_dotenv

# .env load karo (API key ke liye)
load_dotenv()

logger = logging.getLogger(__name__)

# ----------------------------------------
# PROMPT TEMPLATE
# ----------------------------------------
SENTIMENT_PROMPT = """
You are analyzing a multi-speaker meeting transcript.

The meeting could be from ANY domain, including:

- Corporate meetings
- Team meetings
- Client calls
- College or academic meetings
- Interviews
- Government meetings
- General discussions

Your task:

For each speaker or topic block, identify:

• label → speaker name (if available) or topic label  
• sentiment → Positive, Negative, or Neutral  
• score → number between 0.0 and 1.0 showing sentiment strength  
• reason → short explanation  

Also provide overall meeting sentiment.

Definitions:

Positive:
- Agreement
- Approval
- Support
- Satisfaction
- Progress

Negative:
- Disagreement
- Complaints
- Concerns
- Frustration
- Conflict

Neutral:
- Informational discussion
- Status updates
- Procedural conversation
- No emotional tone

Return ONLY valid JSON in this format:

{
  "segments": [
    {
      "label": "Speaker A",
      "sentiment": "Positive",
      "score": 0.75,
      "reason": "Speaker expressed approval"
    }
  ],
  "overall": {
    "sentiment": "Neutral",
    "score": 0.20,
    "summary": "Brief emotional summary of the meeting"
  }
}

Transcript:
"""


# ----------------------------------------
# MAIN CLASS
# ----------------------------------------
class SentimentModule:
    """
    Meeting sentiment analyzer using Groq LLaMA model.
    
    Input:
        transcript text
    
    Output:
        structured sentiment JSON
    """

    def __init__(self):

        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError("GROQ_API_KEY not found in .env")

        # Groq client initialize karo
        self.client = Groq(api_key=api_key)

        # Fast aur accurate model
        self.model = "llama-3.3-70b-versatile"

        logger.info("SentimentModule initialized")

    # ----------------------------------------
    # MAIN FUNCTION
    # ----------------------------------------
    def analyze(self, transcript_text: str) -> dict:

        """
        transcript ka sentiment analyze karta hai
        
        Input:
            plain transcript text
        
        Output:
            JSON dict:
            segments + overall sentiment
        """

        if not transcript_text.strip():
            raise ValueError("Transcript empty hai")

        logger.info("Running sentiment analysis...")

        # Token limit avoid karne ke liye trim karte hai
        trimmed_text = transcript_text[:12000]

        try:

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Return valid JSON only. No explanation."
                    },
                    {
                        "role": "user",
                        "content": SENTIMENT_PROMPT + trimmed_text
                    }
                ],
                temperature=0.2,
                max_tokens=1500
            )

            raw_output = response.choices[0].message.content.strip()

            # Markdown cleaning (LLM kabhi ```json``` me wrap karta hai)
            raw_output = raw_output.replace("```json", "")
            raw_output = raw_output.replace("```", "")
            raw_output = raw_output.strip()

            result = json.loads(raw_output)

            logger.info("Sentiment analysis completed")

            return result

        except json.JSONDecodeError as e:

            logger.error("JSON parse failed")
            logger.error(raw_output)

            raise RuntimeError("Sentiment JSON parsing failed")

        except Exception as e:

            logger.error(f"Sentiment failed: {e}")
            raise e

    # ----------------------------------------
    # DISPLAY FORMAT (UI / Debug)
    # ----------------------------------------
    def format_for_display(self, result: dict) -> str:

        """
        UI ya debug ke liye readable format banata hai
        """

        lines = []

        overall = result.get("overall", {})

        lines.append(
            f"Overall Sentiment: {overall.get('sentiment')} "
            f"(Score: {overall.get('score')})"
        )

        lines.append(overall.get("summary", ""))
        lines.append("")

        for seg in result.get("segments", []):

            lines.append(
                f"{seg.get('label')} → "
                f"{seg.get('sentiment')} "
                f"({seg.get('score')})"
            )

            lines.append(f"Reason: {seg.get('reason')}")
            lines.append("")

        return "\n".join(lines)

    # ----------------------------------------
    # SAVE TO FILE
    # ----------------------------------------
    def save_to_file(
        self,
        result: dict,
        path="transcripts/sentiment.json"
    ):
        """
        sentiment JSON file save karta hai
        """

        os.makedirs("transcripts", exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:

            json.dump(result, f, indent=2)

        logger.info(f"Sentiment saved to {path}")
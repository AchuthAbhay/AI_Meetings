import os
import json
import logging
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

# -----------------------------
# Setup
# -----------------------------
load_dotenv()
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


@dataclass
class ActionItem:
    task: str
    assignee: Optional[str] = None
    deadline: Optional[datetime] = None
    priority: Optional[str] = None
    source_text: str = ""


class ActionItemModule:
    """
    Extract structured action items from meeting transcript
    using Groq LLaMA model.
    """

    def __init__(self):

        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not found in .env")

        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = "llama-3.1-8b-instant"

    # --------------------------------------------------
    # MAIN FUNCTION
    # --------------------------------------------------

    def extract(self, transcript: str) -> List[ActionItem]:

        logger.info("Extracting action items...")

        prompt = f"""
You are an expert meeting action item extractor.

Your job is to extract ONLY real, explicit, assigned action items.

STRICT RULES:

An action item MUST satisfy ALL conditions:

1. A specific task that someone MUST do
2. Must include either:
   - explicit assignee (person, team, role)
   OR
   - implicit responsible party clearly identifiable
3. Must be an executable task — NOT discussion, NOT opinion, NOT decision
4. Must involve future work — NOT something already completed
5. Must be concrete and actionable

DO NOT extract:

- general discussion
- opinions
- complaints
- decisions without assigned execution
- procedural statements
- summaries
- suggestions without assignment
- statements like:
  "we approved the plan"
  "we discussed the budget"
  "council adopted resolution"

ONLY extract tasks like:

CORRECT examples:
- "John will prepare the financial report"
- "Sarah needs to send the proposal by Friday"
- "Engineering team to fix the login bug"
- "Finance department must review expenses"

WRONG examples (DO NOT extract):
- "The plan was approved"
- "Council discussed budget concerns"
- "Taxes increased by 18%"
- "We need to be careful with spending"  ← suggestion, not assignment


For each valid action item extract:

Return JSON format ONLY:

[
  {{
    "task": "clear action starting with verb",
    "assignee": "Full Name or Role or Team or null",
    "deadline": "YYYY-MM-DD or relative date or null",
    "priority": "high | medium | low | null",
    "source_text": "exact quote from transcript"
  }}
]

If NO valid action items exist, return:

[]

Transcript:
{transcript[:6000]}
"""

        try:

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1200
            )

            raw_output = response.choices[0].message.content.strip()

            # Clean accidental markdown
            raw_output = raw_output.replace("```json", "").replace("```", "").strip()

            items_data = json.loads(raw_output)

            items = self._parse_items(items_data)

            logger.info(f"{len(items)} action items extracted")

            return items

        except Exception as e:
            logger.error(f"Action item extraction failed: {e}")
            return []

    # --------------------------------------------------
    # JSON → ActionItem Objects
    # --------------------------------------------------

    def _parse_items(self, items_data: list) -> List[ActionItem]:

        items = []

        for item in items_data:

            deadline = None

            if item.get("deadline"):
                try:
                    deadline = datetime.strptime(item["deadline"], "%Y-%m-%d")
                except ValueError:
                    deadline = None  # keep relative dates as None

            ai = ActionItem(
                task=item.get("task", ""),
                assignee=item.get("assignee"),
                deadline=deadline,
                priority=item.get("priority"),
                source_text=item.get("source_text", "")
            )

            items.append(ai)

        return items

    # --------------------------------------------------
    # Pretty Formatting (for PDF / UI)
    # --------------------------------------------------

    def format_summary(self, items: List[ActionItem]) -> str:

        if not items:
            return "No action items detected."

        lines = [f"{len(items)} Action Items Found:\n"]

        for i, item in enumerate(items, 1):

            lines.append(f"{i}. {item.task}")
            lines.append(f"   Assignee: {item.assignee or 'Unassigned'}")
            lines.append(
                f"   Deadline: {item.deadline.strftime('%Y-%m-%d') if item.deadline else 'Not specified'}"
            )
            lines.append(
                f"   Priority: {item.priority.upper() if item.priority else 'Not specified'}"
            )
            lines.append(f"   Source: {item.source_text[:200]}...\n")

        return "\n".join(lines)

    # --------------------------------------------------
    # Save to JSON
    # --------------------------------------------------

    def save_to_file(self, items: List[ActionItem], filename="transcripts/action_items.json"):

        data = []

        for i in items:
            data.append({
                "task": i.task,
                "assignee": i.assignee,
                "deadline": i.deadline.isoformat() if i.deadline else None,
                "priority": i.priority,
                "source_text": i.source_text
            })

        os.makedirs("transcripts", exist_ok=True)

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved {len(items)} action items to {filename}")
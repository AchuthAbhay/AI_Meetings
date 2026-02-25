from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
import os
import json
from groq import Groq
from dotenv import load_dotenv

# Load .env explicitly from this module's directory
BASEDIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASEDIR, ".env"))

@dataclass
class ActionItem:
    task: str
    assignee: Optional[str] = None
    deadline: Optional[datetime] = None
    priority: Optional[str] = None
    source_text: str = ""

class ActionItemModule:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        if not self.client.api_key:
            raise ValueError("GROQ_API_KEY not found in .env")
        
        self.model = "llama-3.1-8b-instant"  # Fast & cheap

    def extract(self, transcript: str) -> List[ActionItem]:
        """Extract action items from meeting transcript."""
        
        prompt = f"""
            You are an expert meeting analyst. Your task is to extract ALL action items from the meeting transcript below.

            An action item MUST be:
            - A concrete, specific task that someone agreed to do
            - Something measurable or completable (not vague discussions)
            - Triggered by phrases like: "will do", "needs to", "should", "assigned to", "by [date]", "follow up on", "take care of", "responsible for"

            Do NOT include:
            - General discussion points
            - Decisions already made (those go in summary)
            - Vague statements without clear outcomes

            For each action item extract:
            - task: Start with a verb. Clear, specific, actionable (e.g. "Prepare Q1 budget report")
            - assignee: Full name of responsible person. null if unclear
            - deadline: Exact date in YYYY-MM-DD if mentioned, or relative ("next Friday", "end of week"). null if none
            - priority: Infer from urgency/context - "high" (urgent/critical), "medium" (normal), "low" (nice-to-have). null if unclear
            - dependencies: Other tasks this depends on, or null
            - source_text: Exact quote from transcript that triggered this action item (1-2 sentences)

            Return ONLY a valid JSON array. No explanation, no markdown, no extra text:
            [
            {{
                "task": "verb-first actionable description",
                "assignee": "Full Name or null",
                "deadline": "YYYY-MM-DD or relative or null",
                "priority": "high|medium|low or null",
                "dependencies": "description of dependency or null",
                "source_text": "exact quote from transcript"
            }}
            ]

            If no action items found, return: []

            TRANSCRIPT:
            {transcript[:4000]}
        """

        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt + "\n\nTranscript:\n" + transcript[:4000]}],
                temperature=0.1,
                max_tokens=1200
            )
            
            items_data = json.loads(response.choices[0].message.content.strip())
            return self._parse_items(items_data)
            
        except Exception as e:
            print(f"Action item extraction failed: {e}")
            return []

    def _parse_items(self, items_data: list) -> List[ActionItem]:
        """Convert JSON response to ActionItem objects."""
        items = []
        for item in items_data:
            deadline = None
            if item.get('deadline'):
                try:
                    deadline = datetime.strptime(item['deadline'], '%Y-%m-%d')
                except ValueError:
                    pass
            
            ai = ActionItem(
                task=item.get('task', ''),
                assignee=item.get('assignee'),
                deadline=deadline,
                priority=item.get('priority'),
                source_text=item.get('source_text', '')
            )
            items.append(ai)
        return items

    def format_summary(self, items: List[ActionItem]) -> str:
        """Clean, structured format with labels."""
        if not items:
            return "No action items detected."
        
        lines = [f"{len(items)} Action Items Found:"]
        for i, item in enumerate(items, 1):
            lines.append("")
            lines.append(f"{i}. {item.task}")
            lines.append(f"   Assignee: {item.assignee or 'Unassigned'}")
            lines.append(f"   Deadline: {'Not specified' if not item.deadline else item.deadline.strftime('%Y-%m-%d')}")
            lines.append(f"   Priority: {'Not specified' if not item.priority else item.priority.upper()}")
            lines.append(f"   Context: {item.source_text[:200]}...")
            lines.append("")
        
        return "\n".join(lines)


    def save_to_file(self, items: List[ActionItem], filename: str = "action_items.json"):
        """Save action items to JSON file."""
        data = [{"task": i.task, "assignee": i.assignee, "deadline": i.deadline.isoformat() if i.deadline else None,
                 "priority": i.priority, "source_text": i.source_text} for i in items]
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved {len(items)} action items to {filename}")

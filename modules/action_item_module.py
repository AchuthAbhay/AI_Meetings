# action_item_module.py
import os
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


@dataclass
class ActionItem:
    """Data class for action items/tasks extracted from transcripts"""
    task: str
    assignee: Optional[str] = None
    deadline: Optional[str] = None
    priority: Optional[str] = None
    source_text: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'task': self.task,
            'assignee': self.assignee,
            'deadline': self.deadline,
            'priority': self.priority,
            'source_text': self.source_text
        }


class ActionItemModule:
    """Enhanced Action Item Extraction Module with Full Multi-Language Support"""
    
    # Complete language map - 50+ languages
    LANGUAGE_MAP = {
        # Indian Languages
        'hi': 'Hindi', 'mr': 'Marathi', 'ta': 'Tamil', 'te': 'Telugu',
        'bn': 'Bengali', 'gu': 'Gujarati', 'kn': 'Kannada', 'ml': 'Malayalam',
        'pa': 'Punjabi', 'or': 'Odia', 'as': 'Assamese', 'ur': 'Urdu',
        # International Languages
        'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
        'it': 'Italian', 'pt': 'Portuguese', 'ru': 'Russian', 'ja': 'Japanese',
        'ko': 'Korean', 'zh': 'Chinese', 'ar': 'Arabic', 'nl': 'Dutch',
        'pl': 'Polish', 'tr': 'Turkish', 'vi': 'Vietnamese', 'th': 'Thai',
        'el': 'Greek', 'he': 'Hebrew', 'sv': 'Swedish', 'da': 'Danish',
        'fi': 'Finnish', 'no': 'Norwegian', 'cs': 'Czech', 'hu': 'Hungarian',
        'ro': 'Romanian', 'uk': 'Ukrainian', 'id': 'Indonesian', 'ms': 'Malay'
    }

    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not found")
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = "llama-3.3-70b-versatile"
        logger.info("ActionItemModule initialized with full language support")

    def extract(self, transcript: str, output_language: str = 'en') -> List[ActionItem]:
        """Extract action items with full multi-language output support"""
        if not transcript or not transcript.strip():
            return []

        try:
            detected_lang = self._detect_language(transcript)
            output_lang_name = self.LANGUAGE_MAP.get(output_language, 'English')
            logger.info(f"Extracting from {detected_lang}, output in {output_lang_name}")
            
            prompt = self._build_extraction_prompt(transcript, detected_lang, output_language, output_lang_name)
            system_prompt = self._get_system_prompt(output_language, output_lang_name)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=2000
            )

            if not response or not response.choices:
                return self._fallback_extraction(transcript)

            raw_output = response.choices[0].message.content.strip()
            items_data = self._parse_json_response(raw_output)
            
            if not items_data:
                return self._fallback_extraction(transcript)
            
            items = []
            for item in items_data:
                action_item = ActionItem(
                    task=item.get("task", "").strip(),
                    assignee=item.get("assignee"),
                    deadline=item.get("deadline"),
                    priority=item.get("priority"),
                    source_text=item.get("source_text", "")
                )
                if action_item.task and len(action_item.task) > 5:
                    items.append(action_item)
            
            logger.info(f"Extracted {len(items)} action items in {output_lang_name}")
            return items

        except Exception as e:
            logger.error(f"Extraction error: {str(e)}")
            return self._fallback_extraction(transcript)

    def _detect_language(self, text: str) -> str:
        """Detect input language using Unicode ranges"""
        try:
            # Indian language Unicode ranges
            devanagari = re.compile(r'[\u0900-\u097F]')  # Hindi, Marathi, etc.
            tamil = re.compile(r'[\u0B80-\u0BFF]')
            telugu = re.compile(r'[\u0C00-\u0C7F]')
            bengali = re.compile(r'[\u0980-\u09FF]')
            gujarati = re.compile(r'[\u0A80-\u0AFF]')
            kannada = re.compile(r'[\u0C80-\u0CFF]')
            malayalam = re.compile(r'[\u0D00-\u0D7F]')
            punjabi = re.compile(r'[\u0A00-\u0A7F]')
            odia = re.compile(r'[\u0B00-\u0B7F]')
            assamese = re.compile(r'[\u0980-\u09FF]')
            
            counts = {
                'hi': len(devanagari.findall(text)),
                'ta': len(tamil.findall(text)),
                'te': len(telugu.findall(text)),
                'bn': len(bengali.findall(text)),
                'gu': len(gujarati.findall(text)),
                'kn': len(kannada.findall(text)),
                'ml': len(malayalam.findall(text)),
                'pa': len(punjabi.findall(text)),
                'or': len(odia.findall(text)),
                'as': len(assamese.findall(text)),
                'en': len(re.findall(r'[a-zA-Z]', text))
            }
            
            # Find language with highest count
            max_lang = max(counts, key=counts.get)
            if counts[max_lang] > 20:
                return max_lang
            return 'en'
        except:
            return 'en'

    def _get_system_prompt(self, output_lang: str, output_lang_name: str) -> str:
        """System prompt with output language instruction"""
        prompt = f"""You are a task extraction expert. Extract action items from the transcript.
        
CRITICAL: You MUST output the extracted tasks in {output_lang_name} language.

Rules:
- Extract ONLY real action items (future tasks someone will do)
- Each task must start with a verb
- Include assignee if mentioned
- Include deadline if mentioned
- Set priority: high/medium/low based on urgency
- Include the exact source text

Return ONLY valid JSON array. No other text."""

        # Add language-specific instruction for major languages
        lang_instructions = {
            'hi': "\n\nआपको कार्यों को हिंदी में आउटपुट करना है।",
            'mr': "\n\nतुम्हाला कार्ये मराठीत आउटपुट करायची आहेत.",
            'ta': "\n\nநீங்கள் பணிகளை தமிழில் வெளியிட வேண்டும்.",
            'te': "\n\nమీరు పనులను తెలుగులో అవుట్పుట్ చేయాలి.",
            'bn': "\n\nআপনাকে বাংলায় কাজগুলি আউটপুট করতে হবে।",
            'gu': "\n\nતમારે કાર્યોને ગુજરાતીમાં આઉટપુટ કરવાની છે.",
            'kn': "\n\nನೀವು ಕಾರ್ಯಗಳನ್ನು ಕನ್ನಡದಲ್ಲಿ ಔಟ್ಪುಟ್ ಮಾಡಬೇಕು.",
            'ml': "\n\nനിങ്ങൾ ടാസ്ക്കുകൾ മലയാളത്തിൽ ഔട്ട്പുട്ട് ചെയ്യണം.",
            'pa': "\n\nਤੁਹਾਨੂੰ ਕੰਮਾਂ ਨੂੰ ਪੰਜਾਬੀ ਵਿੱਚ ਆਉਟਪੁੱਟ ਕਰਨਾ ਹੈ।",
            'es': "\n\nDebes generar las tareas en español.",
            'fr': "\n\nVous devez sortir les tâches en français.",
            'de': "\n\nSie müssen die Aufgaben auf Deutsch ausgeben.",
            'ja': "\n\nタスクを日本語で出力する必要があります。",
            'zh': "\n\n您需要用中文输出任务。",
            'ar': "\n\nيجب عليك إخراج المهام باللغة العربية.",
            'ru': "\n\nВы должны выводить задачи на русском языке.",
            'pt': "\n\nVocê deve gerar as tarefas em português.",
            'it': "\n\nDevi generare le attività in italiano.",
            'ko': "\n\n한국어로 작업을 출력해야 합니다.",
            'tr': "\n\nGörevleri Türkçe olarak çıkarmalısınız.",
            'vi': "\n\nBạn phải xuất nhiệm vụ bằng tiếng Việt.",
            'th': "\n\nคุณต้องส่งออกงานเป็นภาษาไทย"
        }
        
        return prompt + lang_instructions.get(output_lang, "")

    def _build_extraction_prompt(self, transcript: str, input_lang: str, output_lang: str, output_lang_name: str) -> str:
        """Build extraction prompt with full language support"""
        return f"""
Extract action items from the transcript below.

IMPORTANT: Output the tasks in {output_lang_name} language.

Transcript:
{transcript[:10000]}

Return ONLY valid JSON array. Example:
[
  {{
    "task": "Send the report",
    "assignee": "John",
    "deadline": "Friday",
    "priority": "high",
    "source_text": "John will send the report by Friday"
  }}
]

Extract action items in {output_lang_name}:
"""

    def _parse_json_response(self, raw_output: str) -> List[Dict[str, Any]]:
        """Parse JSON response"""
        try:
            cleaned = raw_output.strip()
            cleaned = re.sub(r'```json\s*', '', cleaned)
            cleaned = re.sub(r'```\s*', '', cleaned)
            data = json.loads(cleaned)
            if isinstance(data, dict):
                data = [data]
            return [item for item in data if isinstance(item, dict) and item.get('task')]
        except:
            try:
                json_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', raw_output)
                if json_match:
                    data = json.loads(json_match.group())
                    if isinstance(data, list):
                        return [item for item in data if isinstance(item, dict) and item.get('task')]
            except:
                pass
            return []

    def _fallback_extraction(self, transcript: str) -> List[ActionItem]:
        """Fallback extraction using regex"""
        items = []
        sentences = re.split(r'[.!?।॥]+', transcript)
        action_words = ['will', 'need to', 'must', 'should', 'करेंगे', 'करना है', 'चाहिए', 'செய்வார்கள்', 'చేస్తారు', 'করবে']
        
        for sentence in sentences[:15]:
            sentence = sentence.strip()
            if len(sentence) > 15 and any(w in sentence.lower() for w in action_words):
                items.append(ActionItem(
                    task=sentence[:150],
                    assignee=None,
                    deadline=None,
                    priority='medium',
                    source_text=sentence
                ))
        return items[:10]

    def get_supported_languages(self) -> Dict[str, str]:
        """Return all supported languages"""
        return self.LANGUAGE_MAP
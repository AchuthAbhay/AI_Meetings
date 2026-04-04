# summarizer_module.py
import os
import json
import logging
import re
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
logger = logging.getLogger(__name__)

class SummarizerModule:
    """
    Enhanced Summarizer Module with Multi-Language Support
    Supports Indian languages: Hindi, Marathi, Tamil, Telugu, Bengali, Gujarati, Kannada, Malayalam, Punjabi
    """

    # Language codes and their display names
    LANGUAGE_MAP = {
        'auto': 'Auto-detect',
        'en': 'English',
        'hi': 'Hindi',
        'mr': 'Marathi',
        'ta': 'Tamil',
        'te': 'Telugu',
        'bn': 'Bengali',
        'gu': 'Gujarati',
        'kn': 'Kannada',
        'ml': 'Malayalam',
        'pa': 'Punjabi',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'ja': 'Japanese',
        'zh': 'Chinese'
    }

    # Language-specific system prompts
    LANGUAGE_PROMPTS = {
        'en': "You are an expert meeting summarizer. Generate summaries in English.",
        'hi': "आप एक विशेषज्ञ मीटिंग सारांशक हैं। कृपया हिंदी में सारांश तैयार करें।",
        'mr': "आप एक तज्ज्ञ मीटिंग सारांशक आहात. कृपया मराठीत सारांश तयार करा.",
        'ta': "நீங்கள் ஒரு நிபுணர் கூட்ட சுருக்ககர்த்தா. தயவுசெய்து தமிழில் சுருக்கத்தை உருவாக்கவும்.",
        'te': "మీరు నిపుణుల సమావేశ సారాంశకర్త. దయచేసి తెలుగులో సారాంశాన్ని రూపొందించండి.",
        'bn': "আপনি একজন বিশেষজ্ঞ মিটিং সারাংশকারী। অনুগ্রহ করে বাংলায় সারাংশ তৈরি করুন।",
        'gu': "તમે એક નિષ્ણાત મીટિંગ સારાંશકર્તા છો. કૃપા કરીને ગુજરાતીમાં સારાંશ બનાવો.",
        'kn': "ನೀವು ತಜ್ಞ ಸಭೆಯ ಸಾರಾಂಶಕಾರರು. ದಯವಿಟ್ಟು ಕನ್ನಡದಲ್ಲಿ ಸಾರಾಂಶವನ್ನು ರಚಿಸಿ.",
        'ml': "നിങ്ങൾ ഒരു വിദഗ്ധ മീറ്റിംഗ് സംഗ്രഹകാരനാണ്. ദയവായി മലയാളത്തിൽ സംഗ്രഹം സൃഷ്ടിക്കുക.",
        'pa': "ਤੁਸੀਂ ਇੱਕ ਮਾਹਿਰ ਮੀਟਿੰਗ ਸੰਖੇਪਕਾਰ ਹੋ। ਕਿਰਪਾ ਕਰਕੇ ਪੰਜਾਬੀ ਵਿੱਚ ਸੰਖੇਪ ਬਣਾਓ।"
    }

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY missing from environment variables")

        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"
        logger.info("SummarizerModule initialized successfully with multi-language support")

    def summarize(self, transcript_text: str, summary_type: str = "executive", 
                  length: str = "medium", include_key_points: bool = True,
                  output_language: str = "auto"):
        """
        Generate a structured summary with multi-language support
        
        Args:
            transcript_text (str): The transcript to summarize
            summary_type (str): Type of summary - "executive", "detailed", or "bullet"
            length (str): Length preference - "short", "medium", or "long"
            include_key_points (bool): Whether to include key decisions and action items
            output_language (str): Target language for summary (auto, en, hi, mr, ta, te, bn, gu, kn, ml, pa)
        
        Returns:
            dict: Structured summary with sections
        """
        try:
            if not transcript_text or not transcript_text.strip():
                raise ValueError("Transcript text is empty")

            # Detect input language if auto is selected
            detected_lang = self._detect_language(transcript_text) if output_language == 'auto' else output_language
            target_lang = detected_lang if output_language == 'auto' else output_language
            
            logger.info(f"Generating {summary_type} summary in {self.LANGUAGE_MAP.get(target_lang, target_lang)}")
            logger.info(f"Input text length: {len(transcript_text)} characters")
            
            # Build prompt based on type, length, and target language
            prompt = self._build_prompt(transcript_text, summary_type, length, include_key_points, target_lang)
            
            # Get language-specific system prompt
            system_prompt = self.LANGUAGE_PROMPTS.get(target_lang, self.LANGUAGE_PROMPTS['en'])
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=self._get_max_tokens(length)
            )

            if not response or not response.choices:
                raise ValueError("No response from Groq API")

            summary_text = response.choices[0].message.content.strip()
            
            if not summary_text:
                raise ValueError("Empty summary generated")

            # Parse and structure the summary
            structured_summary = self._structure_summary(summary_text, summary_type)
            
            # Generate a title from the transcript (in appropriate language)
            title = self._generate_title(transcript_text, target_lang)
            
            # Calculate confidence based on response
            confidence = self._calculate_confidence(summary_text, transcript_text)
            
            return {
                "success": True,
                "summary": structured_summary,
                "title": title,
                "metadata": {
                    "type": summary_type,
                    "length": length,
                    "include_key_points": include_key_points,
                    "word_count": self._count_words(summary_text),
                    "timestamp": datetime.now().isoformat(),
                    "detected_language": self.LANGUAGE_MAP.get(detected_lang, 'English'),
                    "output_language": self.LANGUAGE_MAP.get(target_lang, target_lang),
                    "confidence": confidence,
                    "original_length": len(transcript_text.split())
                }
            }

        except Exception as e:
            logger.error(f"Summarization failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _detect_language(self, text: str) -> str:
        """Detect the language of input text"""
        try:
            # Define Unicode ranges for Indian languages
            hindi_range = re.compile(r'[\u0900-\u097F]')
            tamil_range = re.compile(r'[\u0B80-\u0BFF]')
            telugu_range = re.compile(r'[\u0C00-\u0C7F]')
            bengali_range = re.compile(r'[\u0980-\u09FF]')
            gujarati_range = re.compile(r'[\u0A80-\u0AFF]')
            kannada_range = re.compile(r'[\u0C80-\u0CFF]')
            malayalam_range = re.compile(r'[\u0D00-\u0D7F]')
            punjabi_range = re.compile(r'[\u0A00-\u0A7F]')
            
            # Count occurrences
            counts = {
                'hi': len(hindi_range.findall(text)),
                'ta': len(tamil_range.findall(text)),
                'te': len(telugu_range.findall(text)),
                'bn': len(bengali_range.findall(text)),
                'gu': len(gujarati_range.findall(text)),
                'kn': len(kannada_range.findall(text)),
                'ml': len(malayalam_range.findall(text)),
                'pa': len(punjabi_range.findall(text)),
                'en': len(re.findall(r'[a-zA-Z]', text))
            }
            
            # Get the language with highest count (excluding English if there are Indic characters)
            indic_langs = {k: v for k, v in counts.items() if k != 'en'}
            if any(indic_langs.values()):
                max_lang = max(indic_langs, key=indic_langs.get)
                if counts[max_lang] > 50:  # Minimum threshold for detection
                    return max_lang
            return 'en'
            
        except Exception as e:
            logger.error(f"Language detection failed: {str(e)}")
            return 'en'

    def _build_prompt(self, text, summary_type, length, include_key_points, target_lang):
        """Build the prompt based on parameters with language instruction"""
        
        length_instructions = {
            "short": "Keep it extremely concise (maximum 2-3 sentences). Focus only on the most critical point.",
            "medium": "Provide a balanced summary (4-6 sentences). Cover the main points clearly.",
            "long": "Provide a comprehensive summary (7-10 sentences). Include relevant details and context."
        }
        
        # Add language instruction
        lang_instruction = f"\nIMPORTANT: Generate the summary in {self.LANGUAGE_MAP.get(target_lang, target_lang)} language."
        
        type_instructions = {
            "executive": f"""
Please create an EXECUTIVE SUMMARY with the following sections:
{lang_instruction}

EXECUTIVE SUMMARY:
[Write 2-3 sentences summarizing the main topic and overall outcome]

KEY DECISIONS:
- [List the main decisions made during the meeting]
- [Each decision should be clear and actionable]

ACTION ITEMS:
- [Task] - [Assignee if mentioned, otherwise use "Unassigned"]
- [Include deadlines if mentioned]

KEY TAKEAWAYS:
- [List the most important takeaways from the discussion]

Make each section clear and well-formatted. Use bullet points with dashes (-) for lists.
""",
            "detailed": f"""
Please create a DETAILED SUMMARY with the following sections:
{lang_instruction}

OVERVIEW:
[Write 2-3 sentences introducing the meeting context and main topic]

KEY POINTS DISCUSSED:
- [Point 1 with brief context]
- [Point 2 with brief context]
- [Point 3 with brief context]
- [Continue as needed]

CONCLUSIONS:
- [Main conclusions reached]
- [Agreements made]

NEXT STEPS:
- [Step 1] - [Owner if mentioned]
- [Step 2] - [Owner if mentioned]

Provide thorough coverage of all important discussions and conclusions.
""",
            "bullet": f"""
Please create a BULLET POINT SUMMARY with the key takeaways:
{lang_instruction}

• [Main point 1] - [Brief explanation]
• [Main point 2] - [Brief explanation]
• [Main point 3] - [Brief explanation]
• [Main point 4] - [Brief explanation]
• [Main point 5] - [Brief explanation]

Include 5-7 key points total. Each point should be clear and self-contained.
"""
        }

        key_points_instruction = """
Additionally, please identify and highlight any:
- Critical decisions made
- Action items with assignees
- Important deadlines mentioned
- Key questions raised
""" if include_key_points else ""

        # Truncate text if too long (approximate token limit)
        max_chars = 12000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        prompt = f"""Please summarize the following meeting transcript.

SUMMARY TYPE: {summary_type.upper()}
LENGTH: {length.upper()}

{type_instructions[summary_type]}

LENGTH REQUIREMENT: {length_instructions[length]}

{key_points_instruction}

TRANSCRIPT:
{text}

Generate a well-structured, professional summary following the exact format specified above. Do not use any emojis or special characters. Use simple dashes (-) for bullet points.
"""
        return prompt

    def _get_max_tokens(self, length):
        """Get max tokens based on length preference"""
        return {
            "short": 500,
            "medium": 800,
            "long": 1200
        }.get(length, 800)

    def _count_words(self, text):
        """Count words in text (works for multiple languages)"""
        # Split on whitespace and punctuation for better word count
        words = re.findall(r'[\w\u0900-\u097F\u0B80-\u0BFF\u0C00-\u0C7F\u0980-\u09FF\u0A80-\u0AFF\u0C80-\u0CFF\u0D00-\u0D7F\u0A00-\u0A7F]+', text)
        return len(words)

    def _generate_title(self, text, target_lang):
        """Generate a meaningful title from the transcript in the target language"""
        try:
            # Take first 2-3 sentences or first 100 characters
            sentences = re.split(r'[.!?]+', text)
            if sentences and sentences[0]:
                first_sentence = sentences[0].strip()
                if len(first_sentence) > 80:
                    first_sentence = first_sentence[:77] + "..."
                
                # If target language is not English, we might want to keep original title
                if target_lang != 'en':
                    return first_sentence
                return first_sentence
            return "Meeting Summary"
        except:
            return "Meeting Summary"

    def _structure_summary(self, summary_text, summary_type):
        """Structure the summary with proper sections"""
        
        # If summary already has sections, clean it up
        lines = summary_text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remove any emojis or special characters
            line = re.sub(r'[^\x00-\x7F\u0900-\u097F\u0B80-\u0BFF\u0C00-\u0C7F\u0980-\u09FF\u0A80-\u0AFF\u0C80-\u0CFF\u0D00-\u0D7F\u0A00-\u0A7F]+', '', line)
            # Remove multiple spaces
            line = re.sub(r'\s+', ' ', line).strip()
            if line:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)

    def _calculate_confidence(self, summary, original):
        """Calculate confidence score based on summary quality"""
        try:
            summary_words = self._count_words(summary)
            original_words = self._count_words(original)
            
            if original_words == 0:
                return 0.95
            
            compression_ratio = summary_words / original_words
            # Ideal compression is between 0.1 and 0.3 for good summaries
            if 0.05 <= compression_ratio <= 0.4:
                confidence = 0.95
            elif compression_ratio < 0.05:
                confidence = 0.85
            elif compression_ratio > 0.4:
                confidence = 0.90
            else:
                confidence = 0.80
                
            return round(confidence, 2)
        except:
            return 0.90

    def summarize_document(self, file_path, summary_type="executive", length="medium", output_language="auto"):
        """Summarize a document file with language support"""
        try:
            # Try different encodings
            encodings = ['utf-8', 'latin-1', 'cp1252']
            text = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        text = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if text is None:
                raise ValueError("Could not read file with any supported encoding")
                
            return self.summarize(text, summary_type, length, True, output_language)
        except Exception as e:
            logger.error(f"Document summarization failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_supported_languages(self):
        """Return list of supported languages"""
        return self.LANGUAGE_MAP
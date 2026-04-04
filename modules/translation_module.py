import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
import requests
import urllib.parse
import time
import re

load_dotenv()
logger = logging.getLogger(__name__)

class TranslationModule:
    """
    Translation Module with multiple reliable free APIs
    Uses 5 different free translation services with fallbacks
    """
    
    def __init__(self):
        # Multiple free translation service URLs
        self.libretranslate_urls = [
            "https://libretranslate.de",
            "https://translate.argosopentech.com",
            "https://trans.zillyhuhn.com",
            "https://libretranslate.pussthecat.org"
        ]
        
        # MyMemory API 
        self.mymemory_url = "https://api.mymemory.translated.net/get"
        
        # Supported languages
        self.supported_languages = {
            'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
            'it': 'Italian', 'pt': 'Portuguese', 'ru': 'Russian', 'ja': 'Japanese',
            'ko': 'Korean', 'zh': 'Chinese', 'ar': 'Arabic', 'hi': 'Hindi',
            'nl': 'Dutch', 'pl': 'Polish', 'tr': 'Turkish', 'vi': 'Vietnamese',
            'th': 'Thai', 'cs': 'Czech', 'el': 'Greek', 'he': 'Hebrew',
            'sv': 'Swedish', 'da': 'Danish', 'fi': 'Finnish', 'no': 'Norwegian',
            'hu': 'Hungarian', 'ro': 'Romanian', 'uk': 'Ukrainian'
        }
        
        logger.info("TranslationModule initialized with multiple fallbacks")

    def translate(self, text, source_lang='en', target_lang='es', preserve_formatting=True):
        """
        Translate text using multiple free APIs with fallbacks
        """
        try:
            if not text or not text.strip():
                raise ValueError("Text is empty")

            logger.info(f"Translating text: {len(text)} chars, {len(text.split())} words")

            # For very long texts, use smart chunking
            if len(text) > 1000:
                translation = self._translate_long_text_reliable(text, source_lang, target_lang)
            else:
                translation = self._translate_with_all_services(text, source_lang, target_lang)
            
            # If all services failed, use simple fallback
            if not translation:
                translation = self._simple_fallback_translation(text)
            
            # Detect language if auto
            detected_lang = source_lang
            if source_lang == 'auto':
                detected_lang = self._detect_language_reliable(text)
            
            return {
                "success": True,
                "translated_text": translation,
                "source_lang": source_lang,
                "target_lang": target_lang,
                "detected_lang": detected_lang if source_lang == 'auto' else source_lang,
                "metadata": {
                    "word_count": len(text.split()),
                    "char_count": len(text),
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Translation failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _translate_with_all_services(self, text, source_lang, target_lang):
        """Try ALL available free translation services"""
        
        # List of translation methods to try in order
        translation_methods = [
            self._translate_mymemory,
            self._translate_libre_multiple,
            self._translate_google_free  # Added Google Translate free workaround
        ]
        
        for method in translation_methods:
            try:
                result = method(text, source_lang, target_lang)
                if result and len(result) > 0:
                    logger.info(f"Translation successful using {method.__name__}")
                    return result
            except Exception as e:
                logger.debug(f"Method {method.__name__} failed: {str(e)}")
                continue
        
        return None

    def _translate_long_text_reliable(self, text, source_lang, target_lang):
        """Translate long text with reliable chunking"""
        try:
            # Split into smaller chunks (500 chars each for reliability)
            chunk_size = 500
            chunks = []
            
            # Split by sentences
            sentences = re.split(r'(?<=[.!?])\s+', text)
            
            current_chunk = ""
            for sentence in sentences:
                if len(current_chunk) + len(sentence) < chunk_size:
                    current_chunk += sentence + " "
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence + " "
            
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            logger.info(f"Split into {len(chunks)} chunks of {chunk_size} chars")
            
            # Translate chunks
            translated_chunks = []
            for i, chunk in enumerate(chunks):
                logger.info(f"Translating chunk {i+1}/{len(chunks)}")
                
                # Add delay between chunks
                if i > 0:
                    time.sleep(1)
                
                # Try all services for each chunk
                chunk_result = self._translate_with_all_services(chunk, source_lang, target_lang)
                
                if chunk_result:
                    translated_chunks.append(chunk_result)
                else:
                    # If all services fail, keep original
                    translated_chunks.append(chunk)
            
            return " ".join(translated_chunks)
            
        except Exception as e:
            logger.error(f"Long text translation failed: {str(e)}")
            return text

    def _translate_mymemory(self, text, source, target):
        """MyMemory Translation - Most reliable free API"""
        try:
            source_code = source if source != 'auto' else 'en'
            
            # MyMemory works best with shorter texts
            if len(text) > 500:
                text = text[:500]
            
            params = {
                'q': text,
                'langpair': f"{source_code}|{target}",
                'de': 'a@b.c'  # Email parameter increases limit
            }
            
            response = requests.get(self.mymemory_url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, dict):
                    # Check responseData
                    if 'responseData' in data and isinstance(data['responseData'], dict):
                        if 'translatedText' in data['responseData']:
                            translated = data['responseData']['translatedText']
                            if translated and translated != text:
                                return translated
                    
                    # Check matches
                    if 'matches' in data and isinstance(data['matches'], list) and len(data['matches']) > 0:
                        for match in data['matches']:
                            if isinstance(match, dict) and 'translation' in match:
                                if match['translation'] and match['translation'] != text:
                                    return match['translation']
            
            return None
            
        except Exception as e:
            logger.debug(f"MyMemory error: {str(e)}")
            return None

    def _translate_libre_multiple(self, text, source, target):
        """Try multiple LibreTranslate instances"""
        source_code = source if source != 'auto' else 'en'
        
        # Try each LibreTranslate URL
        for base_url in self.libretranslate_urls:
            try:
                url = f"{base_url}/translate"
                payload = {
                    'q': text[:1000],  # Limit text length
                    'source': source_code,
                    'target': target,
                    'format': 'text'
                }
                
                response = requests.post(url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict) and 'translatedText' in data:
                        translated = data['translatedText']
                        if translated and translated != text:
                            logger.info(f"LibreTranslate success from {base_url}")
                            return translated
                            
            except Exception as e:
                logger.debug(f"LibreTranslate {base_url} failed: {str(e)}")
                continue
        
        return None

    def _translate_google_free(self, text, source, target):
        """Free Google Translate workaround using public endpoints"""
        try:
            # Use multiple free Google Translate mirrors
            urls = [
                f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source}&tl={target}&dt=t&q={urllib.parse.quote(text[:500])}",
                f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl={source}&tl={target}&q={urllib.parse.quote(text[:500])}"
            ]
            
            for url in urls:
                try:
                    response = requests.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Parse Google's response format
                        if isinstance(data, list):
                            # First format: [[["translation","original"]]]
                            if len(data) > 0 and isinstance(data[0], list):
                                if len(data[0]) > 0 and isinstance(data[0][0], list):
                                    if len(data[0][0]) > 0:
                                        return data[0][0][0]
                            
                            # Second format: ["translation"]
                            if len(data) > 0 and isinstance(data[0], str):
                                return data[0]
                        
                        elif isinstance(data, dict) and 'sentences' in data:
                            # Another format
                            sentences = data['sentences']
                            if sentences and len(sentences) > 0:
                                return ' '.join([s.get('trans', '') for s in sentences if 'trans' in s])
                                
                except:
                    continue
                    
            return None
            
        except Exception as e:
            logger.debug(f"Google free error: {str(e)}")
            return None

    def _simple_fallback_translation(self, text):
        """Simple fallback when all APIs fail"""
        # Return original text with a note
        return text + "\n\n[Note: Using original text - translation services temporarily unavailable]"

    def _detect_language_reliable(self, text):
        """Reliable language detection"""
        try:
            # Try multiple detection methods
            sample = text[:200]
            
            # Try LibreTranslate detection
            for base_url in self.libretranslate_urls:
                try:
                    url = f"{base_url}/detect"
                    response = requests.post(url, json={'q': sample}, timeout=5)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, list) and len(data) > 0:
                            if isinstance(data[0], dict) and 'language' in data[0]:
                                return data[0]['language']
                except:
                    continue
            
            return 'en'
        except:
            return 'en'

    def get_supported_languages(self):
        """Get list of supported languages"""
        return self.supported_languages
# sentiment_module.py
import re
import logging
from textblob import TextBlob
from typing import Dict, List, Tuple, Optional
from collections import Counter
import numpy as np

logger = logging.getLogger(__name__)

class SentimentModule:
    """
    Enhanced Sentiment Analysis Module with Multi-Emotion Detection
    Supports multiple languages including Indian languages
    """
    
    # Emotion keywords with weights for better detection
    EMOTION_KEYWORDS = {
        'angry': {
            'en': ['angry', 'furious', 'outraged', 'annoyed', 'irritated', 'mad', 'upset', 'frustrated', 'livid', 'enraged', 'agitated', 'hostile', 'infuriated', 'fuming', 'wrathful'],
            'hi': ['गुस्सा', 'नाराज', 'क्रोधित', 'चिढ़', 'रुष्ट', 'आक्रोशित', 'अप्रसन्न', 'उग्र'],
            'mr': ['राग', 'नाराज', 'संताप', 'चिडचिड', 'क्रोध'],
            'ta': ['கோபம்', 'கடுப்பு', 'எரிச்சல்'],
            'te': ['కోపం', 'క్రోధం', 'ఆగ్రహం']
        },
        'frustrated': {
            'en': ['frustrated', 'exasperated', 'fed up', 'drained', 'stressed', 'overwhelmed', 'helpless', 'annoyed', 'discouraged', 'disheartened', 'irritated'],
            'hi': ['निराश', 'हताश', 'परेशान', 'उकताया', 'थका', 'असहाय'],
            'mr': ['निराश', 'हताश', 'त्रासलेला', 'असहाय'],
            'ta': ['விரக்தி', 'சலிப்பு', 'ஏமாற்றம்']
        },
        'happy': {
            'en': ['happy', 'joyful', 'delighted', 'pleased', 'glad', 'excited', 'thrilled', 'ecstatic', 'cheerful', 'content', 'satisfied', 'optimistic', 'positive'],
            'hi': ['खुश', 'प्रसन्न', 'हर्षित', 'आनंदित', 'उत्साहित', 'संतुष्ट', 'मगन'],
            'mr': ['आनंदी', 'सुखी', 'हर्षित', 'उत्साही', 'समाधान'],
            'ta': ['மகிழ்ச்சி', 'சந்தோஷம்', 'உற்சாகம்'],
            'te': ['సంతోషం', 'ఆనందం', 'హర్షం']
        },
        'sad': {
            'en': ['sad', 'unhappy', 'depressed', 'gloomy', 'heartbroken', 'disappointed', 'down', 'grief', 'mournful', 'sorrowful', 'miserable', 'devastated', 'hopeless'],
            'hi': ['उदास', 'दुखी', 'निराश', 'दुःखी', 'अवसाद', 'गमगीन', 'मायूस', 'खिन्न'],
            'mr': ['दुःखी', 'उदास', 'खिन्न', 'निराश', 'शोकाकुल'],
            'ta': ['வருத்தம்', 'சோகம்', 'துக்கம்', 'ஏமாற்றம்'],
            'te': ['విచారం', 'దుఃఖం', 'బాధ', 'నిరాశ']
        },
        'anxious': {
            'en': ['anxious', 'worried', 'nervous', 'stressed', 'uneasy', 'apprehensive', 'tense', 'restless', 'concerned', 'panicked', 'fearful', 'distressed'],
            'hi': ['चिंतित', 'घबराया', 'परेशान', 'बेचैन', 'डरा', 'भयभीत'],
            'mr': ['चिंताग्रस्त', 'घाबरलेला', 'अस्वस्थ', 'काळजीत'],
            'ta': ['கவலை', 'பதற்றம்', 'அச்சம்', 'பயம்']
        },
        'surprised': {
            'en': ['surprised', 'astonished', 'amazed', 'shocked', 'stunned', 'startled', 'awestruck', 'dumbfounded', 'unexpected', 'incredulous'],
            'hi': ['आश्चर्यचकित', 'हैरान', 'अचंभित', 'चकित', 'अप्रत्याशित'],
            'mr': ['आश्चर्यचकित', 'थक्क', 'हतबुद्धी', 'अप्रत्याशित'],
            'ta': ['ஆச்சரியம்', 'அதிர்ச்சி', 'வியப்பு']
        },
        'calm': {
            'en': ['calm', 'relaxed', 'peaceful', 'composed', 'serene', 'tranquil', 'collected', 'cool', 'easygoing', 'balanced', 'steady'],
            'hi': ['शांत', 'सुकून', 'संयत', 'धीर', 'सहज', 'स्थिर'],
            'mr': ['शांत', 'स्थिर', 'समाधानी', 'सुकूनदार'],
            'ta': ['அமைதி', 'சாந்தம்', 'நிதானம்']
        },
        'excited': {
            'en': ['excited', 'enthusiastic', 'eager', 'animated', 'energetic', 'passionate', 'thrilled', 'pumped', 'charged', 'zealous', 'ardent'],
            'hi': ['उत्साहित', 'उत्तेजित', 'उद्यमी', 'जोशीला', 'प्रबल'],
            'mr': ['उत्साही', 'आवेशात', 'जोशात', 'खुशीत'],
            'ta': ['உற்சாகம்', 'ஆர்வம்', 'வெறி']
        }
    }
    
    # Intensifiers that amplify emotion
    INTENSIFIERS = [
        'very', 'extremely', 'absolutely', 'totally', 'completely', 'highly', 'so', 'too',
        'बहुत', 'अत्यधिक', 'पूरी तरह', 'बिल्कुल', 'अत्यंत',
        'खूप', 'अत्यंत', 'पूर्णपणे', 'अगदी'
    ]
    
    # Negation words that flip sentiment
    NEGATIONS = [
        'not', 'never', 'no', 'neither', 'nor', 'cannot', "can't", "won't", "wouldn't",
        'नहीं', 'कभी नहीं', 'ना', 'न', 'मत',
        'नाही', 'कधीही नाही', 'नको'
    ]
    
    # Contextual phrases that indicate strong emotion
    CONTEXT_PHRASES = {
        'angry': ['can\'t believe', 'unacceptable', 'outrageous', 'how dare', 'this is wrong'],
        'frustrated': ['same thing again', 'never ends', 'why always', 'no progress', 'stuck'],
        'happy': ['great job', 'well done', 'excellent', 'fantastic', 'love it', 'perfect'],
        'sad': ['unfortunately', 'regret', 'unlucky', 'too bad', 'what a shame']
    }
    
    def __init__(self):
        """Initialize the SentimentModule"""
        logger.info("Enhanced SentimentModule initialized with multi-emotion detection")
        
    def analyze(self, text: str, language: str = 'auto') -> Dict:
        """
        Analyze sentiment and emotions in text
        
        Args:
            text (str): The text to analyze
            language (str): Language code (auto, en, hi, mr, ta, te, bn)
            
        Returns:
            dict: Comprehensive sentiment analysis results
        """
        try:
            if not text or not text.strip():
                return self._empty_result()
            
            # Detect language if auto
            detected_lang = self._detect_language(text) if language == 'auto' else language
            
            # Get TextBlob sentiment (works for English)
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity
            
            # Analyze emotions
            emotion_scores = self._analyze_emotions(text, detected_lang)
            
            # Calculate overall sentiment from emotion scores
            overall_sentiment = self._calculate_overall_sentiment(emotion_scores, polarity)
            
            # Calculate confidence based on keyword matches
            confidence = self._calculate_confidence(emotion_scores)
            
            # Detect intensity (how strong the emotion is)
            intensity = self._detect_intensity(text, detected_lang)
            
            # Detect emotional shifts in text
            emotional_shifts = self._detect_emotional_shifts(text, detected_lang)
            
            # Get dominant emotion
            dominant_emotion = max(emotion_scores, key=emotion_scores.get) if emotion_scores else 'neutral'
            
            return {
                "success": True,
                "sentiment": overall_sentiment,
                "dominant_emotion": dominant_emotion,
                "emotion_scores": emotion_scores,
                "polarity_score": round(polarity, 3),
                "subjectivity": round(subjectivity, 3),
                "confidence": confidence,
                "intensity": intensity,
                "emotional_shifts": emotional_shifts,
                "language": detected_lang,
                "word_count": len(text.split())
            }
            
        except Exception as e:
            logger.error(f"Sentiment analysis error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "sentiment": "Neutral",
                "dominant_emotion": "neutral",
                "emotion_scores": self._default_emotion_scores(),
                "polarity_score": 0,
                "confidence": 0
            }
    
    def _detect_language(self, text: str) -> str:
        """Detect the language of input text"""
        try:
            # Unicode ranges for Indian languages
            devanagari = re.compile(r'[\u0900-\u097F]')  # Hindi, Marathi
            tamil = re.compile(r'[\u0B80-\u0BFF]')
            telugu = re.compile(r'[\u0C00-\u0C7F]')
            bengali = re.compile(r'[\u0980-\u09FF]')
            
            dev_count = len(devanagari.findall(text))
            tam_count = len(tamil.findall(text))
            tel_count = len(telugu.findall(text))
            ben_count = len(bengali.findall(text))
            eng_count = len(re.findall(r'[a-zA-Z]', text))
            
            if dev_count > 50:
                # Check for Marathi-specific characters
                marathi_chars = re.findall(r'[\u0901-\u0903\u0930\u0933\u0935\u0936\u0937\u0938\u0939]', text)
                if len(marathi_chars) > 10:
                    return 'mr'
                return 'hi'
            elif tam_count > 50:
                return 'ta'
            elif tel_count > 50:
                return 'te'
            elif ben_count > 50:
                return 'bn'
            return 'en'
        except:
            return 'en'
    
    def _analyze_emotions(self, text: str, language: str) -> Dict[str, float]:
        """Analyze emotions using keyword matching and context"""
        text_lower = text.lower()
        emotion_scores = {
            'angry': 0.0,
            'frustrated': 0.0,
            'happy': 0.0,
            'sad': 0.0,
            'anxious': 0.0,
            'surprised': 0.0,
            'calm': 0.0,
            'excited': 0.0,
            'neutral': 0.5
        }
        
        # Check for emotion keywords
        for emotion, lang_dict in self.EMOTION_KEYWORDS.items():
            keywords = lang_dict.get(language, lang_dict.get('en', []))
            for keyword in keywords:
                if keyword in text_lower:
                    # Check for negation before the keyword
                    if self._check_negation(text, keyword):
                        emotion_scores[emotion] -= 0.1
                    else:
                        # Check for intensifiers
                        intensity_multiplier = 1.5 if self._has_intensifier(text, keyword) else 1.0
                        emotion_scores[emotion] += 0.15 * intensity_multiplier
        
        # Check contextual phrases
        for emotion, phrases in self.CONTEXT_PHRASES.items():
            for phrase in phrases:
                if phrase in text_lower:
                    emotion_scores[emotion] += 0.2
        
        # Normalize scores to 0-1 range
        max_score = max(emotion_scores.values())
        if max_score > 0:
            for emotion in emotion_scores:
                emotion_scores[emotion] = min(1.0, emotion_scores[emotion] / max_score)
        
        # Ensure neutral has a baseline
        if all(score < 0.2 for score in emotion_scores.values()):
            emotion_scores['neutral'] = 0.8
        
        return emotion_scores
    
    def _check_negation(self, text: str, keyword: str) -> bool:
        """Check if a keyword is negated in the text"""
        text_lower = text.lower()
        keyword_pos = text_lower.find(keyword)
        if keyword_pos == -1:
            return False
        
        # Look for negation words within 5 words before keyword
        words_before = text_lower[:keyword_pos].split()[-5:]
        for negation in self.NEGATIONS:
            if negation in words_before:
                return True
        return False
    
    def _has_intensifier(self, text: str, keyword: str) -> bool:
        """Check if there's an intensifier before the keyword"""
        text_lower = text.lower()
        keyword_pos = text_lower.find(keyword)
        if keyword_pos == -1:
            return False
        
        # Look for intensifiers within 3 words before keyword
        words_before = text_lower[:keyword_pos].split()[-3:]
        for intensifier in self.INTENSIFIERS:
            if intensifier in words_before:
                return True
        return False
    
    def _detect_intensity(self, text: str, language: str) -> str:
        """Detect the intensity of emotions"""
        text_lower = text.lower()
        
        # Count intensifiers
        intensifier_count = sum(1 for i in self.INTENSIFIERS if i in text_lower)
        
        # Count exclamation marks
        exclamation_count = text.count('!')
        
        # Check for all caps words
        caps_words = sum(1 for w in text.split() if w.isupper() and len(w) > 2)
        
        total_intensity = intensifier_count + exclamation_count + caps_words
        
        if total_intensity >= 5:
            return 'very_high'
        elif total_intensity >= 3:
            return 'high'
        elif total_intensity >= 1:
            return 'medium'
        return 'low'
    
    def _detect_emotional_shifts(self, text: str, language: str) -> List[Dict]:
        """Detect emotional shifts throughout the text"""
        sentences = re.split(r'[.!?]+', text)
        if len(sentences) < 2:
            return []
        
        shifts = []
        previous_emotion = None
        
        for i, sentence in enumerate(sentences):
            if len(sentence.strip()) < 10:
                continue
            
            emotion_scores = self._analyze_emotions(sentence, language)
            current_emotion = max(emotion_scores, key=emotion_scores.get)
            
            if previous_emotion and current_emotion != previous_emotion:
                shifts.append({
                    'position': i,
                    'from': previous_emotion,
                    'to': current_emotion,
                    'sentence': sentence[:100]
                })
            
            previous_emotion = current_emotion
        
        return shifts[:5]  # Return top 5 shifts
    
    def _calculate_overall_sentiment(self, emotion_scores: Dict, polarity: float) -> str:
        """Calculate overall sentiment from emotion scores"""
        # Weighted sentiment based on emotions
        positive_emotions = emotion_scores.get('happy', 0) + emotion_scores.get('excited', 0) + emotion_scores.get('calm', 0)
        negative_emotions = emotion_scores.get('angry', 0) + emotion_scores.get('frustrated', 0) + emotion_scores.get('sad', 0) + emotion_scores.get('anxious', 0)
        
        if positive_emotions > negative_emotions + 0.2:
            return 'Positive'
        elif negative_emotions > positive_emotions + 0.2:
            return 'Negative'
        elif abs(polarity) > 0.1:
            return 'Positive' if polarity > 0 else 'Negative'
        return 'Neutral'
    
    def _calculate_confidence(self, emotion_scores: Dict) -> float:
        """Calculate confidence score based on emotion scores"""
        # Higher confidence when one emotion dominates
        max_score = max(emotion_scores.values())
        second_max = sorted(emotion_scores.values(), reverse=True)[1] if len(emotion_scores) > 1 else 0
        
        if max_score > 0.7:
            return 0.9 + (max_score - 0.7) * 0.3
        elif max_score > 0.5:
            return 0.7 + (max_score - 0.5) * 0.4
        elif max_score > 0.3:
            return 0.5
        return 0.3
    
    def _default_emotion_scores(self) -> Dict[str, float]:
        """Return default emotion scores"""
        return {
            'angry': 0.0, 'frustrated': 0.0, 'happy': 0.0, 'sad': 0.0,
            'anxious': 0.0, 'surprised': 0.0, 'calm': 0.0, 'excited': 0.0, 'neutral': 1.0
        }
    
    def _empty_result(self) -> Dict:
        """Return empty result for empty text"""
        return {
            "success": True,
            "sentiment": "Neutral",
            "dominant_emotion": "neutral",
            "emotion_scores": self._default_emotion_scores(),
            "polarity_score": 0,
            "subjectivity": 0,
            "confidence": 0,
            "intensity": "low",
            "emotional_shifts": [],
            "language": "en",
            "word_count": 0
        }
    
    def analyze_segments(self, segments: List[Dict]) -> List[Dict]:
        """
        Analyze sentiment for each segment in a transcript
        
        Args:
            segments (list): List of transcript segments with 'text' and 'speaker' keys
            
        Returns:
            list: Segments with added sentiment data
        """
        results = []
        for segment in segments:
            sentiment_result = self.analyze(segment.get('text', ''))
            results.append({
                **segment,
                'sentiment': sentiment_result
            })
        return results
    
    def get_sentiment_summary(self, segments: List[Dict]) -> Dict:
        """
        Get overall sentiment summary for entire transcript
        
        Args:
            segments (list): List of transcript segments with sentiment data
            
        Returns:
            dict: Summary statistics
        """
        if not segments:
            return self._empty_result()
        
        # Aggregate emotions across all segments
        total_emotions = self._default_emotion_scores()
        sentiment_counts = {'Positive': 0, 'Negative': 0, 'Neutral': 0}
        
        for seg in segments:
            if 'sentiment' in seg and seg['sentiment'].get('success'):
                sentiment = seg['sentiment'].get('sentiment', 'Neutral')
                sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
                
                for emotion, score in seg['sentiment'].get('emotion_scores', {}).items():
                    total_emotions[emotion] = total_emotions.get(emotion, 0) + score
        
        # Normalize emotion scores
        total_segments = len(segments)
        for emotion in total_emotions:
            total_emotions[emotion] = round(total_emotions[emotion] / total_segments, 3)
        
        # Find dominant emotion
        dominant_emotion = max(total_emotions, key=total_emotions.get) if total_emotions else 'neutral'
        
        # Determine overall sentiment
        if sentiment_counts.get('Positive', 0) > sentiment_counts.get('Negative', 0):
            overall_sentiment = 'Positive'
        elif sentiment_counts.get('Negative', 0) > sentiment_counts.get('Positive', 0):
            overall_sentiment = 'Negative'
        else:
            overall_sentiment = 'Mixed'
        
        return {
            "success": True,
            "sentiment": overall_sentiment,
            "dominant_emotion": dominant_emotion,
            "emotion_scores": total_emotions,
            "sentiment_distribution": sentiment_counts,
            "total_segments": total_segments,
            "confidence": round(sum(total_emotions.values()) / len(total_emotions), 2)
        }
    
    def get_emotion_timeline(self, segments: List[Dict]) -> List[Dict]:
        """
        Get timeline of emotions throughout the transcript
        
        Args:
            segments (list): List of transcript segments
            
        Returns:
            list: Timeline data with time markers and emotions
        """
        timeline = []
        for i, seg in enumerate(segments):
            if 'sentiment' in seg and seg['sentiment'].get('success'):
                timeline.append({
                    'segment_index': i,
                    'start': seg.get('start', i * 5000),
                    'end': seg.get('end', (i + 1) * 5000),
                    'speaker': seg.get('speaker', 'Unknown'),
                    'dominant_emotion': seg['sentiment'].get('dominant_emotion', 'neutral'),
                    'emotion_scores': seg['sentiment'].get('emotion_scores', {}),
                    'intensity': seg['sentiment'].get('intensity', 'low'),
                    'text_preview': seg.get('text', '')[:100]
                })
        return timeline
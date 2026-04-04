# modules/live_transcription_module.py
import os
import json
import logging
import wave
import io
import base64
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import threading
import queue
import time

import numpy as np
from flask import session

logger = logging.getLogger(__name__)

class LiveTranscriptionModule:
    """
    Multi-language Live Transcription Module
    Supports real-time transcription with original script preservation
    Integrates with TranslationModule for post-translation
    """
    
    def __init__(self):
        """Initialize live transcription module with multi-language support"""
        self.active_sessions = {}
        self.audio_queue = queue.Queue()
        self.transcription_cache = {}
        
        # Language-specific character ranges (Unicode blocks)
        self.unicode_ranges = {
            'hi': {'range': '\u0900-\u097F', 'name': 'Devanagari', 'fonts': ['Noto Sans Devanagari']},
            'mr': {'range': '\u0900-\u097F', 'name': 'Devanagari', 'fonts': ['Noto Sans Devanagari']},
            'bn': {'range': '\u0980-\u09FF', 'name': 'Bengali', 'fonts': ['Noto Sans Bengali']},
            'ta': {'range': '\u0B80-\u0BFF', 'name': 'Tamil', 'fonts': ['Noto Sans Tamil']},
            'te': {'range': '\u0C00-\u0C7F', 'name': 'Telugu', 'fonts': ['Noto Sans Telugu']},
            'gu': {'range': '\u0A80-\u0AFF', 'name': 'Gujarati', 'fonts': ['Noto Sans Gujarati']},
            'kn': {'range': '\u0C80-\u0CFF', 'name': 'Kannada', 'fonts': ['Noto Sans Kannada']},
            'ml': {'range': '\u0D00-\u0D7F', 'name': 'Malayalam', 'fonts': ['Noto Sans Malayalam']},
            'pa': {'range': '\u0A00-\u0A7F', 'name': 'Gurmukhi', 'fonts': ['Noto Sans Gurmukhi']},
            'en': {'range': 'a-zA-Z', 'name': 'Latin', 'fonts': ['Segoe UI', 'Arial']}
        }
        
        # Common phrases in multiple languages for detection
        self.common_phrases = {
            'hi': ['नमस्ते', 'कैसे', 'है', 'मैं', 'आप', 'हम', 'यह', 'वह', 'करना', 'जाना'],
            'mr': ['नमस्कार', 'कसे', 'आहात', 'मी', 'तू', 'आम्ही', 'हे', 'ते', 'करणे', 'जाणे'],
            'bn': ['নমস্কার', 'কেমন', 'আছেন', 'আমি', 'আপনি', 'আমরা', 'এটি', 'সেটি', 'করা', 'যাওয়া'],
            'ta': ['வணக்கம்', 'எப்படி', 'உள்ளது', 'நான்', 'நீங்கள்', 'நாம்', 'இது', 'அது', 'செய்ய', 'செல்'],
            'te': ['నమస్కారం', 'ఎలా', 'ఉంది', 'నేను', 'మీరు', 'మనం', 'ఇది', 'అది', 'చేయండి', 'వెళ్ళు']
        }
        
        logger.info("LiveTranscriptionModule initialized with multi-language support")

    def start_session(self, user_id: str, session_name: str = None) -> Dict:
        """Start a new live transcription session"""
        try:
            session_id = f"live_{user_id}_{int(time.time())}"
            
            session_data = {
                'session_id': session_id,
                'user_id': user_id,
                'session_name': session_name or f"Recording {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                'status': 'active',
                'start_time': datetime.utcnow().isoformat(),
                'transcript_segments': [],
                'detected_languages': set(),
                'audio_chunks': [],
                'total_duration': 0
            }
            
            self.active_sessions[session_id] = session_data
            
            logger.info(f"Started live session: {session_id} for user {user_id}")
            
            return {
                "success": True,
                "session_id": session_id,
                "session": session_data
            }
            
        except Exception as e:
            logger.error(f"Error starting session: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def process_audio_chunk(self, session_id: str, audio_data: bytes, timestamp: str = None) -> Dict:
        """Process incoming audio chunk for transcription"""
        try:
            if session_id not in self.active_sessions:
                return {"success": False, "error": "Session not found"}
            
            session = self.active_sessions[session_id]
            
            # Store audio chunk (for later saving)
            session['audio_chunks'].append({
                'data': audio_data,
                'timestamp': timestamp or datetime.utcnow().isoformat(),
                'size': len(audio_data)
            })
            
            # Update duration (rough estimate)
            session['total_duration'] += len(audio_data) / 16000  # Assuming 16kHz sample rate
            
            return {
                "success": True,
                "message": "Audio chunk processed",
                "chunk_size": len(audio_data)
            }
            
        except Exception as e:
            logger.error(f"Error processing audio chunk: {str(e)}")
            return {"success": False, "error": str(e)}

    def add_transcript_segment(self, session_id: str, text: str, language: str = 'auto', confidence: float = 0.0) -> Dict:
        """Add a transcribed text segment to the session"""
        try:
            if session_id not in self.active_sessions:
                return {"success": False, "error": "Session not found"}
            
            session = self.active_sessions[session_id]
            
            # Detect language if auto
            if language == 'auto':
                language = self.detect_language(text)
            
            # Create segment
            segment = {
                'id': len(session['transcript_segments']) + 1,
                'text': text,
                'language': language,
                'timestamp': datetime.utcnow().isoformat(),
                'confidence': confidence,
                'script': self.unicode_ranges.get(language, {}).get('name', 'Unknown')
            }
            
            session['transcript_segments'].append(segment)
            session['detected_languages'].add(language)
            
            logger.debug(f"Added segment: {text[:50]}... (lang: {language})")
            
            return {
                "success": True,
                "segment": segment,
                "total_segments": len(session['transcript_segments'])
            }
            
        except Exception as e:
            logger.error(f"Error adding transcript segment: {str(e)}")
            return {"success": False, "error": str(e)}

    def detect_language(self, text: str) -> str:
        """Detect language of text based on Unicode ranges and common phrases"""
        if not text:
            return 'en'
        
        # Check Unicode character ranges
        for lang_code, lang_info in self.unicode_ranges.items():
            range_pattern = f"[{lang_info['range']}]"
            if re.search(range_pattern, text):
                # Verify with common phrases for accuracy
                if lang_code in self.common_phrases:
                    for phrase in self.common_phrases[lang_code]:
                        if phrase in text:
                            return lang_code
                return lang_code
        
        # Default to English for Latin script
        if re.search(r'[a-zA-Z]', text):
            return 'en'
        
        return 'en'

    def get_detected_languages(self, session_id: str) -> Dict:
        """Get all languages detected in a session"""
        try:
            if session_id not in self.active_sessions:
                return {"success": False, "error": "Session not found"}
            
            session = self.active_sessions[session_id]
            
            languages = list(session['detected_languages'])
            language_details = []
            
            for lang in languages:
                if lang in self.unicode_ranges:
                    language_details.append({
                        'code': lang,
                        'name': self.unicode_ranges[lang]['name'],
                        'script': self.unicode_ranges[lang]['name']
                    })
            
            return {
                "success": True,
                "languages": languages,
                "language_details": language_details,
                "count": len(languages)
            }
            
        except Exception as e:
            logger.error(f"Error getting detected languages: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_full_transcript(self, session_id: str, preserve_scripts: bool = True) -> Dict:
        """Get the complete transcript preserving original scripts"""
        try:
            if session_id not in self.active_sessions:
                return {"success": False, "error": "Session not found"}
            
            session = self.active_sessions[session_id]
            
            # Build full transcript with language markers
            full_text = ""
            segments_with_lang = []
            
            for segment in session['transcript_segments']:
                full_text += segment['text'] + " "
                segments_with_lang.append({
                    'text': segment['text'],
                    'language': segment['language'],
                    'timestamp': segment['timestamp']
                })
            
            return {
                "success": True,
                "full_text": full_text.strip(),
                "segments": segments_with_lang,
                "total_segments": len(session['transcript_segments']),
                "total_words": len(full_text.split()),
                "languages": list(session['detected_languages']),
                "duration": session['total_duration'],
                "session_name": session['session_name']
            }
            
        except Exception as e:
            logger.error(f"Error getting full transcript: {str(e)}")
            return {"success": False, "error": str(e)}

    def end_session(self, session_id: str) -> Dict:
        """End a live transcription session and save data"""
        try:
            if session_id not in self.active_sessions:
                return {"success": False, "error": "Session not found"}
            
            session = self.active_sessions[session_id]
            session['status'] = 'completed'
            session['end_time'] = datetime.utcnow().isoformat()
            
            # Get complete transcript
            transcript_data = self.get_full_transcript(session_id)
            
            # Prepare final output
            final_data = {
                'session_id': session_id,
                'session_name': session['session_name'],
                'start_time': session['start_time'],
                'end_time': session['end_time'],
                'duration': session['total_duration'],
                'total_segments': len(session['transcript_segments']),
                'detected_languages': list(session['detected_languages']),
                'transcript': transcript_data['full_text'],
                'segments': transcript_data['segments'],
                'audio_chunks_count': len(session['audio_chunks'])
            }
            
            # Cache for retrieval
            self.transcription_cache[session_id] = final_data
            
            # Remove from active sessions after caching
            del self.active_sessions[session_id]
            
            logger.info(f"Ended session: {session_id}")
            
            return {
                "success": True,
                "session_data": final_data
            }
            
        except Exception as e:
            logger.error(f"Error ending session: {str(e)}")
            return {"success": False, "error": str(e)}

    def save_session_to_db(self, session_id: str, user_id: int, db_session) -> Dict:
        """Save session data to database"""
        try:
            if session_id not in self.transcription_cache:
                return {"success": False, "error": "Session not found in cache"}
            
            session_data = self.transcription_cache[session_id]
            
            from models import LiveSession, Transcript
            
            # Create LiveSession record
            live_session = LiveSession(
                user_id=user_id,
                session_name=session_data['session_name'],
                status='completed',
                duration=int(session_data['duration']),
                word_count=len(session_data['transcript'].split()),
                speaker_count=1,  # Can be enhanced with speaker diarization
                detected_language=','.join(session_data['detected_languages']),
                transcript_data=session_data['segments']
            )
            
            db_session.add(live_session)
            db_session.flush()
            
            # Create Transcript record
            transcript = Transcript(
                user_id=user_id,
                filename=f"live_{session_id}.json",
                title=session_data['session_name'],
                duration=session_data['duration'],
                word_count=len(session_data['transcript'].split()),
                speaker_count=1,
                transcript_data={
                    'segments': session_data['segments'],
                    'full_text': session_data['transcript'],
                    'languages': session_data['detected_languages'],
                    'metadata': {
                        'language': 'multi',
                        'language_name': 'Multi-language',
                        'detected_languages': session_data['detected_languages'],
                        'duration': session_data['duration']
                    }
                }
            )
            
            db_session.add(transcript)
            db_session.commit()
            
            return {
                "success": True,
                "live_session_id": live_session.id,
                "transcript_id": transcript.id,
                "message": "Session saved successfully"
            }
            
        except Exception as e:
            logger.error(f"Error saving session to DB: {str(e)}")
            db_session.rollback()
            return {"success": False, "error": str(e)}

    def get_session_history(self, user_id: int, db_session, limit: int = 50) -> Dict:
        """Get user's live transcription history from database"""
        try:
            from models import LiveSession
            
            sessions = db_session.query(LiveSession).filter_by(
                user_id=user_id
            ).order_by(
                LiveSession.created_at.desc()
            ).limit(limit).all()
            
            history = []
            for session in sessions:
                history.append({
                    'id': session.id,
                    'session_name': session.session_name,
                    'duration': session.duration,
                    'word_count': session.word_count,
                    'detected_language': session.detected_language,
                    'created_at': session.created_at.isoformat() if session.created_at else None,
                    'transcript_preview': session.transcript_data[:3] if session.transcript_data else []
                })
            
            return {
                "success": True,
                "history": history,
                "total": len(history)
            }
            
        except Exception as e:
            logger.error(f"Error getting session history: {str(e)}")
            return {"success": False, "error": str(e)}

    def merge_segments(self, segments: List[Dict]) -> Dict:
        """Merge consecutive segments with same language"""
        if not segments:
            return {"success": True, "merged_segments": []}
        
        merged = []
        current = segments[0].copy()
        
        for segment in segments[1:]:
            if segment['language'] == current['language']:
                current['text'] += " " + segment['text']
            else:
                merged.append(current)
                current = segment.copy()
        
        merged.append(current)
        
        return {
            "success": True,
            "merged_segments": merged,
            "original_count": len(segments),
            "merged_count": len(merged)
        }

    def format_transcript_for_display(self, segments: List[Dict]) -> str:
        """Format transcript with language-specific styling"""
        if not segments:
            return ""
        
        formatted_parts = []
        for segment in segments:
            lang_code = segment['language']
            lang_info = self.unicode_ranges.get(lang_code, self.unicode_ranges['en'])
            
            # Add language-specific wrapper with font information
            formatted = f'<span class="lang-{lang_code}" data-lang="{lang_code}" style="font-family: {", ".join(lang_info["fonts"])};">{segment["text"]}</span>'
            formatted_parts.append(formatted)
        
        return " ".join(formatted_parts)

    def get_language_stats(self, segments: List[Dict]) -> Dict:
        """Get statistics about language usage in transcript"""
        if not segments:
            return {"success": True, "stats": {}}
        
        lang_stats = {}
        total_chars = 0
        
        for segment in segments:
            lang = segment['language']
            text = segment['text']
            char_count = len(text)
            word_count = len(text.split())
            
            if lang not in lang_stats:
                lang_stats[lang] = {
                    'char_count': 0,
                    'word_count': 0,
                    'segment_count': 0,
                    'text_samples': []
                }
            
            lang_stats[lang]['char_count'] += char_count
            lang_stats[lang]['word_count'] += word_count
            lang_stats[lang]['segment_count'] += 1
            total_chars += char_count
            
            # Store sample text (first 100 chars)
            if len(lang_stats[lang]['text_samples']) < 3:
                lang_stats[lang]['text_samples'].append(text[:100])
        
        # Calculate percentages
        for lang in lang_stats:
            lang_stats[lang]['percentage'] = round(
                (lang_stats[lang]['char_count'] / total_chars) * 100, 2
            ) if total_chars > 0 else 0
        
        return {
            "success": True,
            "stats": lang_stats,
            "total_segments": len(segments),
            "total_languages": len(lang_stats)
        }


# Create global instance
live_transcriber = LiveTranscriptionModule()
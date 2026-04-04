# transcription.py

import os
import time
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
BASE_URL = "https://api.assemblyai.com/v2"


class TranscriptionModule:
    """
    AssemblyAI Transcription Module with multilingual support
    Supports 99+ languages including all major Indian languages
    """

    # Language mapping for display
    LANGUAGE_NAMES = {
        'hi': 'Hindi',
        'mr': 'Marathi',
        'ta': 'Tamil',
        'te': 'Telugu',
        'bn': 'Bengali',
        'gu': 'Gujarati',
        'kn': 'Kannada',
        'ml': 'Malayalam',
        'pa': 'Punjabi',
        'or': 'Odia',
        'as': 'Assamese',
        'ur': 'Urdu',
        'en': 'English',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'ja': 'Japanese',
        'zh': 'Chinese',
        'auto': 'Auto-detected'
    }

    def __init__(self):
        if not ASSEMBLYAI_API_KEY:
            raise ValueError("ASSEMBLYAI_API_KEY not found in environment variables")

        self.headers = {
            "authorization": ASSEMBLYAI_API_KEY,
            "content-type": "application/json"
        }
        logger.info("TranscriptionModule initialized with AssemblyAI")

    def transcribe_file(self, audio_path, language_code=None, speaker_labels=True):
        """
        Transcribe an audio file with support for multiple languages
        
        Args:
            audio_path: Path to audio file
            language_code: Language code (hi, ta, te, etc.) or None for auto-detect
            speaker_labels: Enable speaker diarization
        
        Returns:
            dict: Formatted transcript with segments and metadata
        """
        try:
            logger.info(f"Starting transcription for file: {audio_path}")
            logger.info(f"Language setting: {language_code or 'auto-detect'}")
            
            # Upload audio file
            upload_url = self._upload_audio(audio_path)
            logger.info("Audio uploaded successfully")
            
            # Start transcription with language parameter
            transcript_id = self._start_transcription(upload_url, language_code, speaker_labels)
            logger.info(f"Transcription started with ID: {transcript_id}")
            
            # Poll for completion
            data = self._poll(transcript_id)
            logger.info("Transcription completed successfully")
            
            # Format and return the result
            return self._format_output(data, language_code)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during transcription: {str(e)}")
            raise Exception(f"Network error: Failed to connect to AssemblyAI API. Please check your internet connection.")
            
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise Exception(f"Transcription failed: {str(e)}")

    def _upload_audio(self, audio_path):
        """Upload audio file to AssemblyAI"""
        try:
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            file_size = os.path.getsize(audio_path)
            if file_size == 0:
                raise ValueError("Audio file is empty")
            
            logger.info(f"Uploading file: {audio_path} (Size: {file_size/1024/1024:.2f} MB)")
            
            with open(audio_path, "rb") as f:
                response = requests.post(
                    f"{BASE_URL}/upload",
                    headers={"authorization": ASSEMBLYAI_API_KEY},
                    data=f,
                    timeout=300
                )

            response.raise_for_status()
            upload_url = response.json()["upload_url"]
            logger.info(f"File uploaded successfully")
            
            return upload_url
            
        except Exception as e:
            logger.error(f"Upload failed: {str(e)}")
            raise Exception(f"Upload failed: {str(e)}")

    def _start_transcription(self, upload_url, language_code=None, speaker_labels=True):
        """Start transcription job with language support - FIXED API PARAMETERS"""
        try:
            # Base payload - FIXED: speech_model is deprecated, using speech_models array
            payload = {
                "audio_url": upload_url,
                "speaker_labels": speaker_labels,
                "punctuate": True,
                "format_text": True,
            }
            
            # Add language code if specified (not auto)
            if language_code and language_code != 'auto':
                payload["language_code"] = language_code
                # Use specific model for single language
                payload["speech_models"] = ["best"]
                logger.info(f"Using specified language: {language_code}")
            else:
                # For auto-detection, use universal-2 model
                payload["speech_models"] = ["universal-2"]
                payload["language_detection"] = True
                logger.info("Using auto language detection with universal-2 model")

            logger.info(f"Starting transcription with config: {payload}")
            
            response = requests.post(
                f"{BASE_URL}/transcript",
                headers=self.headers,
                json=payload,
                timeout=30
            )

            response.raise_for_status()
            result = response.json()
            
            if "id" not in result:
                raise Exception("No transcript ID received from API")
                
            return result["id"]
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error: {e.response.text}")
            raise Exception(f"API Error: {e.response.text}")
        except Exception as e:
            logger.error(f"Failed to start transcription: {str(e)}")
            raise Exception(f"Failed to start transcription: {str(e)}")

    def _poll(self, transcript_id, max_attempts=120):
        """Poll for transcription completion"""
        attempts = 0
        start_time = time.time()
        
        while attempts < max_attempts:
            try:
                response = requests.get(
                    f"{BASE_URL}/transcript/{transcript_id}",
                    headers=self.headers,
                    timeout=30
                )

                response.raise_for_status()
                data = response.json()

                if data["status"] == "completed":
                    elapsed_time = time.time() - start_time
                    logger.info(f"Transcription completed in {elapsed_time:.2f} seconds")
                    return data

                elif data["status"] == "error":
                    error_msg = data.get("error", "Unknown error occurred")
                    logger.error(f"Transcription error: {error_msg}")
                    raise Exception(f"Transcription failed: {error_msg}")

                elif data["status"] in ["queued", "processing"]:
                    logger.debug(f"Transcription {data['status']}...")

                # Exponential backoff
                time.sleep(min(3 * (attempts + 1), 10))
                attempts += 1

            except Exception as e:
                logger.error(f"Polling error: {str(e)}")
                time.sleep(5)
                attempts += 1

        raise Exception("Transcription timeout: Maximum polling attempts exceeded")

    def _format_output(self, data, requested_language=None):
        """Format the transcription output with speaker segments"""
        try:
            segments = []
            
            # Get utterances (speaker-separated segments)
            utterances = data.get("utterances", [])
            
            if utterances:
                for idx, u in enumerate(utterances):
                    segments.append({
                        "speaker": f"Speaker {chr(65 + idx % 26)}",  # A, B, C...
                        "text": u.get("text", "").strip(),
                        "start": u.get("start", 0),
                        "end": u.get("end", 0),
                        "confidence": u.get("confidence", 1.0)
                    })
            else:
                # Fallback to single speaker if no utterances
                text = data.get("text", "").strip()
                if text:
                    segments.append({
                        "speaker": "Speaker A",
                        "text": text,
                        "start": 0,
                        "end": data.get("audio_duration", 0) * 1000,
                        "confidence": data.get("confidence", 1.0)
                    })

            # Get detected language information
            detected_language = data.get("language_code", "en")
            language_name = self.LANGUAGE_NAMES.get(detected_language, detected_language)
            
            # Calculate metadata
            total_words = sum(len(s["text"].split()) for s in segments)
            audio_duration = data.get("audio_duration", 0)
            
            # Format audio duration
            if audio_duration:
                minutes = int(audio_duration // 60)
                seconds = int(audio_duration % 60)
                duration_str = f"{minutes}:{seconds:02d}"
            else:
                duration_str = "0:00"

            # Get unique speakers count
            speaker_count = len(set(s["speaker"] for s in segments))

            return {
                "segments": segments,
                "metadata": {
                    "id": data.get("id", ""),
                    "duration": audio_duration,
                    "duration_formatted": duration_str,
                    "total_words": total_words,
                    "speaker_count": speaker_count,
                    "language": detected_language,
                    "language_name": language_name,
                    "confidence": data.get("confidence", 0.95),
                    "created": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error formatting output: {str(e)}")
            return {
                "segments": [{
                    "speaker": "Speaker A",
                    "text": data.get("text", "No transcript available")
                }],
                "metadata": {
                    "error": "Error formatting transcript",
                    "language": "en",
                    "language_name": "English"
                }
            }

    def get_language_name(self, language_code):
        """Get display name for language code"""
        return self.LANGUAGE_NAMES.get(language_code, language_code)

    def get_supported_languages(self):
        """Get dictionary of supported languages"""
        return self.LANGUAGE_NAMES

    def get_transcript_status(self, transcript_id):
        """Get status of a transcription job"""
        try:
            response = requests.get(
                f"{BASE_URL}/transcript/{transcript_id}",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Error getting transcript status: {str(e)}")
            return {"status": "error", "error": str(e)}

    def delete_transcript(self, transcript_id):
        """Delete a transcript from AssemblyAI"""
        try:
            response = requests.delete(
                f"{BASE_URL}/transcript/{transcript_id}",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            logger.info(f"Transcript {transcript_id} deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting transcript: {str(e)}")
            return False
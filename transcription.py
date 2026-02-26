import os
import time
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
BASE_URL = "https://api.assemblyai.com/v2"


class TranscriptionModule:
    """
    AssemblyAI-based transcription + speaker diarization module
    Whisper replacement
    """

    def __init__(self):

        if not ASSEMBLYAI_API_KEY:
            raise ValueError("ASSEMBLYAI_API_KEY not found")

        self.headers = {
            "authorization": ASSEMBLYAI_API_KEY,
            "content-type": "application/json"
        }

    def transcribe_file(self, audio_path):

        logger.info("Uploading audio to AssemblyAI...")

        upload_url = self._upload_audio(audio_path)

        logger.info("Starting transcription...")

        transcript_id = self._start_transcription(upload_url)

        logger.info("Waiting for transcription...")

        data = self._poll(transcript_id)

        logger.info("Transcription complete")

        return self._format_output(data)

    def _upload_audio(self, audio_path):

        with open(audio_path, "rb") as f:

            response = requests.post(
                f"{BASE_URL}/upload",
                headers={"authorization": ASSEMBLYAI_API_KEY},
                data=f
            )

        response.raise_for_status()

        return response.json()["upload_url"]

    def _start_transcription(self, upload_url):

        payload = {
            "audio_url": upload_url,
            "speaker_labels": True,
            "auto_chapters": False
        }

        response = requests.post(
            f"{BASE_URL}/transcript",
            headers=self.headers,
            json=payload
        )

        response.raise_for_status()

        return response.json()["id"]

    def _poll(self, transcript_id):

        while True:

            response = requests.get(
                f"{BASE_URL}/transcript/{transcript_id}",
                headers=self.headers
            )

            response.raise_for_status()

            data = response.json()

            if data["status"] == "completed":
                return data

            if data["status"] == "error":
                raise RuntimeError(data["error"])

            time.sleep(3)

    def _format_output(self, data):

        segments = []

        for u in data["utterances"]:

            segments.append({

                "speaker": f"Speaker {u['speaker']}",

                "start": u["start"] / 1000,

                "end": u["end"] / 1000,

                "text": u["text"]

            })

        word_count = sum(len(s["text"].split()) for s in segments)

        duration = segments[-1]["end"] if segments else 0

        transcript = {

            "segments": segments,

            "metrics": {

                "word_count": word_count,

                "duration": duration,

                "avg_confidence": 0.95

            }

        }

        return transcript
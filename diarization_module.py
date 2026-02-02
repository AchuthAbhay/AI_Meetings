import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
ASSEMBLYAI_BASE_URL = "https://api.assemblyai.com/v2"


class DiarizationModule:
    """
    Speaker diarization using AssemblyAI.
    This module is intentionally isolated so it can be
    replaced later (e.g., PyAnnote) without touching the rest of the system.
    """

    def __init__(self):
        if not ASSEMBLYAI_API_KEY:
            raise ValueError("ASSEMBLYAI_API_KEY not found in environment")

        self.headers = {
            "authorization": ASSEMBLYAI_API_KEY,
            "content-type": "application/json"
        }

    def diarize(self, audio_path: str):
        """
        Returns diarized segments:
        [
          {
            "speaker": "Speaker A",
            "start": 12.34,
            "end": 18.90,
            "text": "Hello everyone..."
          }
        ]
        """

        audio_url = self._upload_audio(audio_path)
        transcript_id = self._start_transcription(audio_url)
        transcript_data = self._poll_transcription(transcript_id)

        return self._format_segments(transcript_data)

    # ---------------- INTERNAL METHODS ---------------- #

    def _upload_audio(self, audio_path: str) -> str:
        with open(audio_path, "rb") as f:
            response = requests.post(
                f"{ASSEMBLYAI_BASE_URL}/upload",
                headers={"authorization": ASSEMBLYAI_API_KEY},
                data=f
            )
        response.raise_for_status()
        return response.json()["upload_url"]

    def _start_transcription(self, audio_url: str) -> str:
        payload = {
            "audio_url": audio_url,
            "speaker_labels": True
        }

        response = requests.post(
            f"{ASSEMBLYAI_BASE_URL}/transcript",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()["id"]

    def _poll_transcription(self, transcript_id: str) -> dict:
        while True:
            response = requests.get(
                f"{ASSEMBLYAI_BASE_URL}/transcript/{transcript_id}",
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()

            status = data["status"]

            if status == "completed":
                return data
            if status == "error":
                raise RuntimeError(data["error"])

            time.sleep(3)

    def _format_segments(self, transcript_data: dict):
        segments = []

        for item in transcript_data.get("utterances", []):
            segments.append({
                "speaker": f"Speaker {item['speaker']}",
                "start": item["start"] / 1000.0,
                "end": item["end"] / 1000.0,
                "text": item["text"]
            })

        return segments

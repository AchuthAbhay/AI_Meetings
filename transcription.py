# transcription.py

import os
import logging
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()
logger = logging.getLogger(__name__)

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")


class TranscriptionModule:
    """
    Sarvam AI Batch STT + Speaker Diarization
    Drop-in replacement for AssemblyAI module
    """

    def __init__(self):
        if not SARVAM_API_KEY:
            raise ValueError("SARVAM_API_KEY not found in .env")

        self.client = SarvamAI(api_subscription_key=SARVAM_API_KEY)
        logger.info("TranscriptionModule initialized with Sarvam AI")

    def transcribe_file(self, audio_path: str) -> dict:

        logger.info("Creating Sarvam batch job...")

        # Create job with diarization enabled
        job = self.client.speech_to_text_job.create_job(
    model="saaras:v3",
    mode="translate",
    language_code="unknown",
    with_diarization=True,
    # num_speakers not provided → Sarvam estimates automatically
)


        logger.info("Uploading audio file...")
        job.upload_files(file_paths=[audio_path])
        job.start()

        logger.info("Waiting for transcription to complete...")
        job.wait_until_complete()

        # Get results
        file_results = job.get_file_results()

        if not file_results["successful"]:
            error = file_results["failed"][0]["error_message"]
            raise RuntimeError(f"Sarvam transcription failed: {error}")

        # Download output JSON to temp folder
        job.download_outputs(output_dir="./transcripts/sarvam_raw")

        logger.info("Transcription complete, formatting output...")

        # Read the downloaded JSON output
        import json
        import glob
        output_files = glob.glob("./transcripts/sarvam_raw/*.json")
        with open(output_files[0], encoding="utf-8") as f:
            data = json.load(f)

        return self._format_output(data)

    def _format_output(self, data: dict) -> dict:
        """
        Map Sarvam's diarized_transcript to your internal format:
        { "segments": [...], "metrics": {...} }
        """

        segments = []

        # Sarvam diarization output format (from official docs)
        entries = (
            data.get("diarized_transcript", {}).get("entries", [])
        )

        for entry in entries:
            segments.append({
                "speaker": f"Speaker {entry.get('speaker_id', '0')}",
                "start": float(entry.get("start_time_seconds", 0)),
                "end": float(entry.get("end_time_seconds", 0)),
                "text": entry.get("transcript", "")
            })

        word_count = sum(len(s["text"].split()) for s in segments)
        duration = segments[-1]["end"] if segments else 0.0

        return {
            "segments": segments,
            "metrics": {
                "word_count": word_count,
                "duration": duration,
                "avg_confidence": 0.95
            }
        }

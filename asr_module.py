import whisper
import torch
import os
import logging
import math
import subprocess
from typing import List, Dict

# Setup logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/asr_module.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create chunk folder
CHUNKS_DIR = "audio_chunks"
os.makedirs(CHUNKS_DIR, exist_ok=True)


class ASRModule:
    def __init__(self, model_name="small"):
        """
        Initialize Whisper model
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")
        self.model = whisper.load_model(model_name, device=self.device)
        logger.info(f"Loaded Whisper model '{model_name}' on {self.device}")

    def split_audio(self, file_path: str, chunk_length_sec: int = 300, overlap_sec: int = 5) -> List[str]:
        """
        Split audio into chunks with small overlap to avoid cutting words
        """
        try:
            # Get duration
            result = subprocess.run(
                ["ffprobe", "-i", file_path, "-show_entries", "format=duration",
                 "-v", "quiet", "-of", "csv=p=0"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            total_duration = float(result.stdout.strip())
            logger.info(f"Audio duration: {total_duration:.2f} seconds")

            chunk_files = []
            num_chunks = math.ceil(total_duration / chunk_length_sec)
            logger.info(f"Splitting into {num_chunks} chunks...")

            for i in range(num_chunks):
                start = max(i * chunk_length_sec - overlap_sec, 0)
                chunk_file = os.path.join(CHUNKS_DIR, f"chunk_{i}.wav")

                subprocess.run([
                    "ffmpeg", "-y", "-i", file_path,
                    "-ss", str(start),
                    "-t", str(chunk_length_sec + overlap_sec),
                    "-ac", "1", "-ar", "16000", chunk_file
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                chunk_files.append(chunk_file)

            return chunk_files

        except Exception as e:
            logger.error("Error in split_audio", exc_info=True)
            raise e

    def transcribe_file(self, file_path: str) -> Dict:
        """
        Transcribe audio file with:
        ✔ timestamp offset
        ✔ overlap boundary removal
        ✔ sorted segments
        """
        try:
            all_segments = []
            chunk_files = self.split_audio(file_path)

            last_end_time = 0.0   # Track overlap removal

            for idx, chunk in enumerate(chunk_files):
                logger.info(f"Transcribing chunk {idx + 1}/{len(chunk_files)}")

                result = self.model.transcribe(
                    chunk,
                    fp16=True if self.device == "cuda" else False,
                    task="transcribe",
                    verbose=False,
                    temperature=0,
                    no_speech_threshold=0.1,
                    condition_on_previous_text=False
                )

                base_offset = idx * 300   # global offset for chunk

                for seg in result['segments']:
                    seg_start = seg['start'] + base_offset
                    seg_end = seg['end'] + base_offset

                    # Skip duplicates if overlapping region produces repeated lines
                    if seg_end <= last_end_time + 0.25:
                        continue

                    seg['start'] = seg_start
                    seg['end'] = seg_end
                    all_segments.append(seg)
                    last_end_time = seg_end

            # Sort by start time
            all_segments = sorted(all_segments, key=lambda s: s['start'])

            # Compute simple metrics
            word_count = sum(len(seg['text'].split()) for seg in all_segments)
            duration = all_segments[-1]['end'] if all_segments else 0
            avg_confidence = sum(seg.get('avg_logprob', -1) for seg in all_segments) / max(len(all_segments), 1)

            transcript = {
                "segments": all_segments,
                "metrics": {
                    "word_count": word_count,
                    "duration": duration,
                    "avg_confidence": avg_confidence
                }
            }

            # Cleanup
            for f in chunk_files:
                os.remove(f)

            return transcript

        except Exception as e:
            logger.error("Error in transcribe_file", exc_info=True)
            raise e
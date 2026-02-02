from flask import Flask, request, jsonify, render_template, send_file
from asr_module import ASRModule
from summarizer_module import SummarizerModule

# OPTIONAL diarization (safe import)
try:
    from diarization_module import DiarizationModule
    from merge_diarization import merge_whisper_with_diarization
    DIARIZATION_AVAILABLE = True
except ImportError:
    DIARIZATION_AVAILABLE = False

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
import os
import json
import logging

# -------------------------
# Setup
# -------------------------
app = Flask(__name__)

UPLOAD_DIR = "uploads"
TRANSCRIPTS_DIR = "transcripts"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

asr = ASRModule()
summarizer = SummarizerModule()

# Initialize diarization only if available
diarizer = DiarizationModule() if DIARIZATION_AVAILABLE else None

# -------------------------
# Routes
# -------------------------
@app.route("/")
def index():
    return render_template("index.html")

# -------------------------
# TRANSCRIBE (Whisper + optional Diarization)
# -------------------------
@app.route("/transcribe", methods=["POST"])
def transcribe():
    audio = request.files.get("audio")
    if not audio:
        return jsonify({"success": False, "error": "No audio uploaded"}), 400

    audio_path = os.path.join(UPLOAD_DIR, audio.filename)
    audio.save(audio_path)
    logger.info(f"Saved audio: {audio_path}")

    # ---- Whisper transcription ----
    transcript = asr.transcribe_file(audio_path)

    whisper_segments = transcript["segments"]

    merged_segments = None

    # ---- Optional diarization ----
    if DIARIZATION_AVAILABLE:
        try:
            diarization_segments = diarizer.diarize(audio_path)
            merged_segments = merge_whisper_with_diarization(
                whisper_segments,
                diarization_segments
            )
            logger.info("Diarization merged successfully")
        except Exception as e:
            logger.warning(f"Diarization failed, falling back to Whisper only: {e}")

    # ---- Save files ----
    with open(os.path.join(TRANSCRIPTS_DIR, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(transcript, f, indent=2)

    if merged_segments:
        with open(os.path.join(TRANSCRIPTS_DIR, "merged.json"), "w", encoding="utf-8") as f:
            json.dump(merged_segments, f, indent=2)

    return jsonify({
        "success": True,
        "transcript": transcript,
        "merged_transcript": merged_segments
    })

# -------------------------
# SUMMARY (uses merged transcript if available)
# -------------------------
@app.route("/summarize", methods=["POST"])
def summarize():
    merged_path = os.path.join(TRANSCRIPTS_DIR, "merged.json")
    transcript_path = os.path.join(TRANSCRIPTS_DIR, "latest.json")

    if os.path.exists(merged_path):
        with open(merged_path, encoding="utf-8") as f:
            merged = json.load(f)

        full_text = "\n".join(
            f"[{seg['speaker']}] {seg['text']}"
            for seg in merged
        )
    elif os.path.exists(transcript_path):
        with open(transcript_path, encoding="utf-8") as f:
            data = json.load(f)

        full_text = " ".join(seg["text"] for seg in data["segments"])
    else:
        return jsonify({"success": False, "error": "No transcript found"}), 400

    summary = summarizer.summarize(full_text)

    with open(os.path.join(TRANSCRIPTS_DIR, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary)

    return jsonify({"success": True, "summary": summary})

# -------------------------
# DOWNLOAD SUMMARY PDF
# -------------------------
@app.route("/download_pdf", methods=["GET"])
def download_summary():
    summary_path = os.path.join(TRANSCRIPTS_DIR, "summary.txt")
    if not os.path.exists(summary_path):
        return "No summary available", 400

    with open(summary_path, encoding="utf-8") as f:
        summary_text = f.read()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Professional Meeting Summary", styles["Heading1"]),
        Spacer(1, 12)
    ]

    for block in summary_text.split("\n\n"):
        if block.strip():
            elements.append(Paragraph(block.replace("\n", " "), styles["BodyText"]))
            elements.append(Spacer(1, 8))

    doc.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="meeting_summary.pdf",
        mimetype="application/pdf"
    )

# -------------------------
# Run App
# -------------------------
if __name__ == "__main__":
    app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200MB
    app.run(host="0.0.0.0", port=5000, debug=True)


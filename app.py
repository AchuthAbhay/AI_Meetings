from flask import Flask, request, jsonify, render_template, send_file
from summarizer_module import SummarizerModule
from action_item_module import ActionItemModule
from sentiment_module import SentimentModule
from transcription import TranscriptionModule

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO

import os
import json
import logging


# =========================
# Setup
# =========================

app = Flask(__name__)

UPLOAD_DIR = "uploads"
TRANSCRIPTS_DIR = "transcripts"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =========================
# Initialize Modules
# =========================

# AssemblyAI unified transcription + diarization
asr = TranscriptionModule()

summarizer = SummarizerModule()

action_extractor = ActionItemModule()

sentiment_module = SentimentModule()


# =========================
# Routes
# =========================

@app.route("/")
def index():
    return render_template("index.html")


# =========================
# TRANSCRIBE (AssemblyAI unified)
# =========================

@app.route("/transcribe", methods=["POST"])
def transcribe():

    audio = request.files.get("audio")

    if not audio:
        return jsonify({
            "success": False,
            "error": "No audio uploaded"
        }), 400

    audio_path = os.path.join(UPLOAD_DIR, audio.filename)

    audio.save(audio_path)

    logger.info(f"Saved audio: {audio_path}")


    try:

        # AssemblyAI transcription with diarization
        transcript = asr.transcribe_file(audio_path)

        # Save unified transcript
        with open(os.path.join(TRANSCRIPTS_DIR, "latest.json"), "w", encoding="utf-8") as f:
            json.dump(transcript, f, indent=2)

        return jsonify({
            "success": True,
            "transcript": transcript
        })

    except Exception as e:

        logger.error(f"Transcription error: {e}")

        return jsonify({
            "success": False,
            "error": str(e)
        })


# =========================
# SUMMARY
# =========================

@app.route("/summarize", methods=["POST"])
def summarize():

    transcript_path = os.path.join(TRANSCRIPTS_DIR, "latest.json")

    if not os.path.exists(transcript_path):

        return jsonify({
            "success": False,
            "error": "No transcript found. Please transcribe first."
        })

    with open(transcript_path, encoding="utf-8") as f:

        data = json.load(f)


    # Use speaker labeled transcript
    full_text = "\n".join(
        f"{seg.get('speaker', 'Speaker')}: {seg.get('text', '')}"
        for seg in data["segments"]
    )


    summary = summarizer.summarize(full_text)


    with open(os.path.join(TRANSCRIPTS_DIR, "summary.txt"), "w", encoding="utf-8") as f:

        f.write(summary)


    return jsonify({
        "success": True,
        "summary": summary
    })


# =========================
# ACTION ITEMS
# =========================

@app.route("/action_items", methods=["POST"])
def action_items():

    transcript_path = os.path.join(TRANSCRIPTS_DIR, "latest.json")

    if not os.path.exists(transcript_path):

        return jsonify({
            "success": False,
            "error": "No transcript found. Please transcribe first."
        })


    with open(transcript_path, encoding="utf-8") as f:

        data = json.load(f)


    full_text = "\n".join(
        f"{seg.get('speaker', 'Speaker')}: {seg.get('text', '')}"
        for seg in data["segments"]
    )


    items = action_extractor.extract(full_text)

    action_extractor.save_to_file(items)


    return jsonify({

        "success": True,

        "count": len(items),

        "formatted": action_extractor.format_summary(items),

        "items": [

            {
                "task": i.task,
                "assignee": i.assignee,
                "deadline": str(i.deadline) if i.deadline else None,
                "priority": i.priority,
                "source_text": i.source_text
            }

            for i in items
        ]
    })


# =========================
# SENTIMENT ANALYSIS
# =========================

@app.route("/sentiment", methods=["POST"])
def sentiment():

    transcript_path = os.path.join(TRANSCRIPTS_DIR, "latest.json")

    if not os.path.exists(transcript_path):

        return jsonify({
            "success": False,
            "error": "No transcript found"
        })


    with open(transcript_path) as f:

        data = json.load(f)


    transcript_text = "\n".join(
        f"{seg.get('speaker', 'Speaker')}: {seg.get('text', '')}"
        for seg in data["segments"]
    )


    result = sentiment_module.analyze(transcript_text)

    sentiment_module.save_to_file(result)


    return jsonify({

        "success": True,

        "result": result

    })


# =========================
# DOWNLOAD PDF
# =========================

@app.route("/download_pdf", methods=["GET"])
def download_pdf():

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

        Paragraph("Meeting Summary", styles["Heading1"]),

        Spacer(1, 12)

    ]


    for block in summary_text.split("\n\n"):

        if block.strip():

            elements.append(

                Paragraph(block.replace("\n", " "), styles["BodyText"])

            )

            elements.append(Spacer(1, 8))


    doc.build(elements)

    buffer.seek(0)


    return send_file(

        buffer,

        as_attachment=True,

        download_name="meeting_summary.pdf",

        mimetype="application/pdf"

    )


# =========================
# Run
# =========================

if __name__ == "__main__":

    app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
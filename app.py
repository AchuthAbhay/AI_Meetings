from flask import Flask, request, jsonify, render_template, send_file
from asr_module import ASRModule
from summarizer_module import SummarizerModule
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
import logging
import json
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

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

asr = ASRModule()              # Your Whisper ASR module
summarizer = SummarizerModule()  # Your Perplexity / structured summary module

# -------------------------
# Routes
# -------------------------
@app.route("/")
def index():
    """Render main page"""
    return render_template("index.html")

@app.route("/transcribe", methods=["POST"])   # ye audio upload krne k liye hai aur uska transcription krne k liye hai
def transcribe():
    """Handle audio upload and transcription"""
    audio = request.files.get("audio")
    if not audio:
        return jsonify({"success": False, "error": "No audio uploaded"}), 400

    path = os.path.join(UPLOAD_DIR, audio.filename)
    audio.save(path)
    logger.info(f"Saved audio file: {path}")

    transcript = asr.transcribe_file(path)

    transcript_path = os.path.join(TRANSCRIPTS_DIR, "latest.json")
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(transcript, f, ensure_ascii=False, indent=2)

    return jsonify({"success": True, "transcript": transcript})

@app.route("/summarize", methods=["POST"])             #ye structured summary generate krne k liye hai
def summarize():
    """Generate structured summary from latest transcript"""
    transcript_path = os.path.join(TRANSCRIPTS_DIR, "latest.json")
    if not os.path.exists(transcript_path):
        return jsonify({"success": False, "error": "No transcript found"}), 400

    with open(transcript_path, encoding="utf-8") as f:
        data = json.load(f)

    full_text = " ".join(seg["text"] for seg in data["segments"])
    summary = summarizer.summarize(full_text)

    summary_txt_path = os.path.join(TRANSCRIPTS_DIR, "summary.txt")
    with open(summary_txt_path, "w", encoding="utf-8") as f:
        f.write(summary)

    return jsonify({"success": True, "summary": summary})

@app.route("/download_pdf", methods=["GET", "POST"])     # ye summary pdf download krne k liye hai
def download_summary():
    """Download summary as properly formatted PDF"""
    summary_txt_path = os.path.join(TRANSCRIPTS_DIR, "summary.txt")
    if not os.path.exists(summary_txt_path):
        return "No summary available", 400

    with open(summary_txt_path, encoding="utf-8") as f:
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
    elements = []
    elements.append(Paragraph("Meeting Summary", styles['Heading1']))
    elements.append(Spacer(1, 12))
    
    for para in summary_text.split('\n\n'):
        if para.strip():
            text = para.replace('\n', ' ').strip()
            elements.append(Paragraph(text, styles['BodyText']))
            elements.append(Spacer(1, 6))
    
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
    # Allow big uploads if needed
    app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 MB
    app.run(host="0.0.0.0", port=5000, debug=True)

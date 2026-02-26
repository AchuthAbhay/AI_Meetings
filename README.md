
---

🎙️ AudioToAction — Intelligent Meeting Minutes Generator

AudioToAction is an end-to-end AI system that automatically converts meeting audio into structured, actionable meeting minutes. It performs transcription, speaker identification, summarization, sentiment analysis, and action-item extraction — transforming raw conversations into meaningful insights.

This project is designed for real-world use cases such as corporate meetings, academic discussions, team standups, and government or organizational sessions.


---

🚀 Key Features

1. Speech-to-Text Transcription

Converts audio files (WAV, MP3, M4A, FLAC) into accurate text transcripts

Preserves timestamps for each spoken segment

Supports long audio files with efficient processing


2. Speaker Identification (Diarization)

Automatically detects and labels different speakers

Produces structured transcript format:


[Speaker A]: Project deadline is next Friday.
[Speaker B]: I will complete the report before Thursday.


---

3. AI-Generated Professional Meeting Summary

Automatically generates structured summaries including:

Executive Summary

Key Decisions

Concerns and Discussions

Important Quotes


Powered by advanced LLM models via Perplexity Sonar-Pro.


---

4. Action Item Extraction

Identifies actionable tasks from meeting conversations:

Example output:

Task: Prepare financial report
Assignee: John
Deadline: Next Friday
Priority: High

Uses LLaMA-based LLM via Groq API.


---

5. Sentiment Analysis

Analyzes emotional tone of meeting:

Positive / Neutral / Negative classification

Speaker-level sentiment breakdown

Overall meeting sentiment summary


Example:

Overall Sentiment: Negative
Reason: Concerns about tax increase and public dissatisfaction


---

6. PDF Export

Generates professional meeting summary PDF for documentation and sharing.


---

🧠 System Architecture

Pipeline:

Audio Input
   ↓
Transcription + Speaker Detection
   ↓
Structured Transcript
   ↓
├── Summary Generation
├── Action Item Extraction
├── Sentiment Analysis
↓
Final Meeting Minutes + PDF Export


---

🛠️ Tech Stack

Backend

Python

Flask


AI / ML Models

AssemblyAI (Transcription + Diarization)

Perplexity Sonar-Pro (Summarization)

Groq LLaMA-3 (Action Items & Sentiment)


NLP Libraries

Transformers

SentencePiece


Frontend

HTML

CSS

JavaScript


Other Tools

ReportLab (PDF generation)

REST APIs

JSON-based structured storage



---

📂 Project Structure

AUDIOTOACTION/
│
├── app.py
├── transcription.py
├── summarizer_module.py
├── action_item_module.py
├── sentiment_module.py
│
├── templates/
├── static/
├── uploads/
├── transcripts/
├── logs/
│
├── requirements.txt
└── README.md


---

🎯 Use Cases

This system can be used for:

Corporate meetings

Academic lectures

Team standups

Client meetings

Research interviews

Government discussions

Project management tracking



---

🧪 Current Capabilities

✔ Audio → Transcript
✔ Speaker Identification
✔ Structured Meeting Summary
✔ Action Item Extraction
✔ Sentiment Analysis
✔ PDF Export
✔ Web Interface


---

🔮 Future Improvements

Planned features:

Fully offline transcription option

Real-time meeting analysis

Speaker name identification

Meeting analytics dashboard

Topic segmentation

Searchable transcript database



---

👨‍💻 Contributors
    Achuth Abhay
    Sarthak Marathe
    Harshada Godse

Developed as part of an AI/ML project to automate meeting intelligence and workflow automation.


---

⭐ Why This Project Matters

Meetings generate valuable information, but extracting actionable insights manually is slow and inefficient.

AudioToAction automates this entire process using AI, saving time and improving productivity.


---


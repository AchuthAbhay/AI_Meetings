# app.py
import os
import json
import logging
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO

from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_file
from werkzeug.utils import secure_filename

# Import configuration
from config import Config

# Import extensions
from extensions import db, login_manager, migrate

# Import models
from models import *

# Import AI modules
from modules.transcription import TranscriptionModule
from modules.summarizer_module import SummarizerModule
from modules.action_item_module import ActionItemModule
from modules.sentiment_module import SentimentModule
from modules.translation_module import TranslationModule
from modules.live_transcription_module import live_transcriber
from modules.youtube_processor import YouTubeProcessor
from services.chat_service import chat_service
from services.rag_index_service import rag_index_service

# Initialize app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login_page'
migrate.init_app(app, db)

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize AI modules
asr = TranscriptionModule()
summarizer = SummarizerModule()
action_extractor = ActionItemModule()
sentiment_analyzer = SentimentModule()
translator = TranslationModule()
youtube_processor = YouTubeProcessor()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store active live sessions
active_sessions = {}

# ========== HELPER FUNCTIONS ==========

def get_local_file_path(user_id, filename, subfolder=''):
    """Get local file path for storing files"""
    folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id), subfolder)
    os.makedirs(folder, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_filename = secure_filename(filename)
    return os.path.join(folder, f"{timestamp}_{safe_filename}")

def format_srt_time(ms):
    """Format milliseconds to SRT time format"""
    if not ms:
        return "00:00:00,000"
    seconds = ms / 1000
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(ms % 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def index_transcript_safely(transcript):
    """Best-effort indexing into Qdrant without blocking the main flow."""
    try:
        indexed = rag_index_service.index_transcript(transcript)
        if indexed:
            logger.info("Indexed transcript %s into Qdrant", transcript.id)
        else:
            logger.info("Skipped Qdrant indexing for transcript %s", transcript.id)
    except Exception as error:
        logger.warning("Transcript indexing failed for %s: %s", getattr(transcript, "id", "unknown"), error)

# ========== BEFORE REQUEST HANDLER ==========
@app.before_request
def before_request():
    """Handle route permissions"""
    public_routes = ['/', '/index', '/home', '/login', '/signup', 
                     '/api/login', '/api/signup', '/api/contact', '/static', '/api/health']
    
    for route in public_routes:
        if request.path.startswith(route):
            return None
    
    if request.path.startswith('/api/'):
        if not session.get('user_id'):
            return jsonify({"success": False, "error": "Authentication required"}), 401
        return None
    
    if not session.get('user_id'):
        return redirect(url_for('login_page'))
    
    return None

# ========== USER LOADER ==========
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ========== AUTH DECORATOR ==========
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def api_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({"success": False, "error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    user_id = session.get('user_id')
    return db.session.get(User, user_id) if user_id else None

# ========== AUTH ROUTES ==========
@app.route("/")
def root():
    return render_template("index.html")

@app.route("/index")
def index_redirect():
    return redirect(url_for('root'))

@app.route("/home")
def home_redirect():
    return redirect(url_for('root'))

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/signup")
def signup_page():
    return render_template("signup.html")

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    remember = data.get('remember', False)
    
    if not email or not password:
        return jsonify({"success": False, "error": "Email and password required"}), 400
    
    user = User.query.filter_by(email=email).first()
    
    if user and user.check_password(password):
        session['user_id'] = user.id
        session['user_email'] = user.email
        session.permanent = remember
        
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Login successful",
            "user": user.to_dict()
        })
    
    return jsonify({"success": False, "error": "Invalid email or password"}), 401

@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json()
    
    first_name = data.get('firstName', '')
    last_name = data.get('lastName', '')
    email = data.get('email', '')
    password = data.get('password', '')
    security_level = data.get('securityLevel', 'standard')
    security_pin = data.get('securityPin', '')
    use_case = data.get('useCase', 'work')
    newsletter = data.get('newsletter', False)
    
    username = email.split('@')[0]
    full_name = f"{first_name} {last_name}".strip()
    
    if not first_name or not last_name or not email or not password:
        return jsonify({"success": False, "error": "All fields are required"}), 400
    
    if '@' not in email or '.' not in email:
        return jsonify({"success": False, "error": "Invalid email format"}), 400
    
    if len(password) < 6:
        return jsonify({"success": False, "error": "Password must be at least 6 characters"}), 400
    
    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "error": "Email already registered"}), 400
    
    if User.query.filter_by(username=username).first():
        import random
        username = f"{username}{random.randint(100, 999)}"
    
    try:
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            job_title='New User',
            department=use_case
        )
        user.set_password(password)
        
        settings = UserSettings(
            user=user,
            email_notifications=newsletter,
            desktop_notifications=True,
            theme='dark',
            sidebar_collapsed=False,
            security_level=security_level,
            security_pin=security_pin if security_pin else None
        )
        
        db.session.add(user)
        db.session.add(settings)
        db.session.commit()
        
        logger.info(f"New user registered: {email}")
        
        return jsonify({
            "success": True,
            "message": "Account created successfully",
            "user": user.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        db.session.rollback()
        return jsonify({"success": False, "error": "Failed to create account. Please try again."}), 500

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"})

@app.route("/api/contact", methods=["POST"])
def api_contact():
    data = request.get_json()
    
    name = data.get('name')
    email = data.get('email')
    company = data.get('company')
    interest = data.get('interest')
    message = data.get('message')
    
    if not name or not email or not message:
        return jsonify({"success": False, "error": "Please fill in all required fields"}), 400
    
    logger.info(f"Contact form submission from {name} ({email}) - Interest: {interest}")
    
    return jsonify({
        "success": True,
        "message": "Thank you for contacting us! We'll get back to you soon."
    })

# ========== PAGE ROUTES (Protected) ==========
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/upload-transcribe")
@login_required
def upload_transcribe():
    return render_template("upload_transcribe.html")

@app.route("/live-transcription")
@login_required
def live_transcription():
    return render_template("live_transcription.html")

@app.route("/summarization")
@login_required
def summarization_page():
    return render_template("summarization.html")

@app.route("/ai-chat")
@login_required
def ai_chat_page():
    return render_template("ai_chat.html")

@app.route("/my-tasks")
@login_required
def my_tasks_page():
    return render_template("my_tasks.html")

@app.route("/sentiment-analysis")
@login_required
def sentiment_page():
    return render_template("sentiment_analysis.html")

@app.route("/speaker-identification")
@login_required
def speaker_identification():
    return render_template("speaker_identification.html")

@app.route("/translation")
@login_required
def translation_page():
    return render_template("translation.html")

@app.route("/files-history")
@login_required
def files_history():
    return render_template("files_history.html")

@app.route("/analytics")
@login_required
def analytics_page():
    return render_template("analytics.html")

@app.route("/calendar")
@login_required
def calendar_page():
    return render_template("calendar.html")

@app.route("/profile")
@login_required
def profile_page():
    return render_template("profile.html")

# ========== USER PROFILE API ==========
@app.route("/api/user/profile", methods=["GET"])
@api_login_required
def get_user_profile():
    user = get_current_user()
    settings = user.settings
    
    return jsonify({
        "success": True,
        "user": user.to_dict(),
        "settings": {
            "email_notifications": settings.email_notifications,
            "desktop_notifications": settings.desktop_notifications,
            "theme": settings.theme,
            "sidebar_collapsed": settings.sidebar_collapsed,
            "security_level": getattr(settings, 'security_level', 'standard')
        }
    })

@app.route("/api/user/profile", methods=["PUT"])
@api_login_required
def update_user_profile():
    data = request.get_json()
    user = get_current_user()
    
    if 'full_name' in data:
        user.full_name = data['full_name']
    if 'job_title' in data:
        user.job_title = data['job_title']
    if 'department' in data:
        user.department = data['department']
    if 'email' in data and data['email'] != user.email:
        if User.query.filter_by(email=data['email']).first():
            return jsonify({"success": False, "error": "Email in use"}), 400
        user.email = data['email']
        session['user_email'] = data['email']
    
    db.session.commit()
    return jsonify({"success": True, "user": user.to_dict()})

@app.route("/api/user/settings", methods=["PUT"])
@api_login_required
def update_user_settings():
    data = request.get_json()
    user = get_current_user()
    settings = user.settings
    
    if 'email_notifications' in data:
        settings.email_notifications = data['email_notifications']
    if 'desktop_notifications' in data:
        settings.desktop_notifications = data['desktop_notifications']
    if 'theme' in data:
        settings.theme = data['theme']
    if 'sidebar_collapsed' in data:
        settings.sidebar_collapsed = data['sidebar_collapsed']
    
    db.session.commit()
    return jsonify({"success": True})

# ========== API ENDPOINT FOR RECENT TRANSCRIPTS ==========
@app.route("/api/recent-transcripts", methods=["GET"])
@api_login_required
def get_recent_transcripts():
    """Get recent transcripts for summarization input"""
    user_id = session['user_id']
    limit = request.args.get('limit', 10, type=int)
    
    transcripts = Transcript.query.filter_by(user_id=user_id)\
        .order_by(Transcript.created_at.desc())\
        .limit(limit)\
        .all()
    
    result = []
    for t in transcripts:
        # Extract transcript text from stored data
        transcript_text = ""
        if t.transcript_data and 'segments' in t.transcript_data:
            transcript_text = " ".join([s.get('text', '') for s in t.transcript_data['segments']])
        elif t.transcript_data and 'text' in t.transcript_data:
            transcript_text = t.transcript_data['text']
        
        result.append({
            "id": t.id,
            "name": t.title or t.filename,
            "text": transcript_text[:500] + "..." if len(transcript_text) > 500 else transcript_text,
            "full_text": transcript_text,
            "duration": t.duration,
            "word_count": t.word_count,
            "speaker_count": t.speaker_count,
            "language": t.transcript_data.get('metadata', {}).get('language', 'en') if t.transcript_data else 'en',
            "language_name": t.transcript_data.get('metadata', {}).get('language_name', 'English') if t.transcript_data else 'English',
            "timestamp": t.created_at.isoformat() if t.created_at else None,
            "created_at_formatted": t.created_at.strftime("%b %d, %Y") if t.created_at else ""
        })
    
    return jsonify({
        "success": True,
        "transcripts": result
    })

@app.route("/api/audio/<int:session_id>", methods=["GET"])
@api_login_required
def get_audio_file(session_id):
    """Serve audio file for a live session"""
    session_obj = LiveSession.query.get_or_404(session_id)
    
    if session_obj.user_id != session['user_id']:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    if not session_obj.audio_path or not os.path.exists(session_obj.audio_path):
        return jsonify({"success": False, "error": "Audio file not found"}), 404
    
    return send_file(
        session_obj.audio_path,
        mimetype='audio/webm',
        as_attachment=False
    )

# ========== LIVE TRANSCRIPTION MODULE INTEGRATION ==========

@app.route("/api/live/start", methods=["POST"])
@api_login_required
def live_start_session():
    """Start a new live transcription session"""
    data = request.get_json() or {}
    session_name = data.get('session_name')
    
    user_id = session['user_id']
    result = live_transcriber.start_session(str(user_id), session_name)
    
    if result['success']:
        return jsonify({
            "success": True,
            "session_id": result['session_id'],
            "message": "Session started"
        })
    else:
        return jsonify({"success": False, "error": result['error']}), 500


@app.route("/api/live/segment", methods=["POST"])
@api_login_required
def live_add_segment():
    """Add a transcribed segment to live session"""
    data = request.get_json()
    session_id = data.get('session_id')
    text = data.get('text', '')
    language = data.get('language', 'auto')
    confidence = data.get('confidence', 0.0)
    
    if not session_id or not text:
        return jsonify({"success": False, "error": "Missing required fields"}), 400
    
    result = live_transcriber.add_transcript_segment(session_id, text, language, confidence)
    
    if result['success']:
        return jsonify({
            "success": True,
            "segment": result['segment'],
            "total_segments": result['total_segments']
        })
    else:
        return jsonify({"success": False, "error": result['error']}), 500


@app.route("/api/live/transcript", methods=["GET"])
@api_login_required
def live_get_transcript():
    """Get current transcript of live session"""
    session_id = request.args.get('session_id')
    
    if not session_id:
        return jsonify({"success": False, "error": "session_id required"}), 400
    
    result = live_transcriber.get_full_transcript(session_id)
    
    if result['success']:
        return jsonify({
            "success": True,
            "transcript": result['full_text'],
            "segments": result['segments'],
            "languages": result['languages'],
            "total_words": result['total_words']
        })
    else:
        return jsonify({"success": False, "error": result['error']}), 500


@app.route("/api/live/languages", methods=["GET"])
@api_login_required
def live_get_languages():
    """Get detected languages in live session"""
    session_id = request.args.get('session_id')
    
    if not session_id:
        return jsonify({"success": False, "error": "session_id required"}), 400
    
    result = live_transcriber.get_detected_languages(session_id)
    
    if result['success']:
        return jsonify({
            "success": True,
            "languages": result['languages'],
            "language_details": result['language_details'],
            "count": result['count']
        })
    else:
        return jsonify({"success": False, "error": result['error']}), 500


@app.route("/api/live/end", methods=["POST"])
@api_login_required
def live_end_session():
    """End live transcription session and save to database"""
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({"success": False, "error": "session_id required"}), 400
    
    # End session
    end_result = live_transcriber.end_session(session_id)
    
    if not end_result['success']:
        return jsonify({"success": False, "error": end_result['error']}), 500
    
    # Save to database
    from extensions import db
    save_result = live_transcriber.save_session_to_db(session_id, session['user_id'], db)
    
    if save_result['success']:
        transcript = db.session.get(Transcript, save_result['transcript_id'])
        if transcript:
            index_transcript_safely(transcript)
        return jsonify({
            "success": True,
            "session_data": end_result['session_data'],
            "db_ids": {
                "live_session_id": save_result['live_session_id'],
                "transcript_id": save_result['transcript_id']
            },
            "message": "Session saved successfully"
        })
    else:
        return jsonify({"success": False, "error": save_result['error']}), 500


@app.route("/api/live/history", methods=["GET"])
@api_login_required
def live_get_history():
    """Get user's live transcription history"""
    limit = request.args.get('limit', 50, type=int)
    
    from extensions import db
    result = live_transcriber.get_session_history(session['user_id'], db, limit)
    
    if result['success']:
        return jsonify({
            "success": True,
            "history": result['history'],
            "total": result['total']
        })
    else:
        return jsonify({"success": False, "error": result['error']}), 500


@app.route("/api/live/merge-segments", methods=["POST"])
@api_login_required
def live_merge_segments():
    """Merge consecutive segments with same language"""
    data = request.get_json()
    segments = data.get('segments', [])
    
    if not segments:
        return jsonify({"success": False, "error": "segments required"}), 400
    
    result = live_transcriber.merge_segments(segments)
    
    if result['success']:
        return jsonify({
            "success": True,
            "merged_segments": result['merged_segments'],
            "original_count": result['original_count'],
            "merged_count": result['merged_count']
        })
    else:
        return jsonify({"success": False, "error": result['error']}), 500


@app.route("/api/live/language-stats", methods=["POST"])
@api_login_required
def live_language_stats():
    """Get language statistics for transcript segments"""
    data = request.get_json()
    segments = data.get('segments', [])
    
    if not segments:
        return jsonify({"success": False, "error": "segments required"}), 400
    
    result = live_transcriber.get_language_stats(segments)
    
    if result['success']:
        return jsonify({
            "success": True,
            "stats": result['stats'],
            "total_segments": result['total_segments'],
            "total_languages": result['total_languages']
        })
    else:
        return jsonify({"success": False, "error": result['error']}), 500


# Enhanced translation route that works with live transcript segments
@app.route("/api/translate-full", methods=["POST"])
@api_login_required
def translate_full_transcript():
    """Translate entire transcript to target language using the translation module"""
    data = request.get_json()
    text = data.get("text", "")
    source_lang = data.get("source_lang", "auto")
    target_lang = data.get("target_lang", "en")
    segments = data.get("segments", [])
    
    if not text and not segments:
        return jsonify({"success": False, "error": "No text provided"}), 400
    
    # If segments are provided, use them for better context
    if segments and isinstance(segments, list):
        # Combine text from segments
        text = " ".join([seg.get('text', '') for seg in segments if seg.get('text')])
    
    if not text.strip():
        return jsonify({"success": False, "error": "No text to translate"}), 400
    
    try:
        # Use your existing translation module
        result = translator.translate(text, source_lang, target_lang)
        
        if result.get("success"):
            # Save translation to database
            from models import Translation
            from extensions import db
            
            translation = Translation(
                user_id=session['user_id'],
                source_text=text[:500] if len(text) > 500 else text,
                translated_text=result['translated_text'],
                source_lang=result.get('detected_lang', source_lang),
                target_lang=target_lang,
                confidence=0.9,
                word_count=len(text.split())
            )
            
            db.session.add(translation)
            db.session.commit()
            
            # Get language name for display
            lang_names = translator.get_supported_languages()
            lang_name = lang_names.get(target_lang, target_lang.upper())
            
            return jsonify({
                "success": True,
                "translation": result['translated_text'],
                "source_lang": result.get('detected_lang', source_lang),
                "target_lang": target_lang,
                "target_lang_name": lang_name,
                "db_id": translation.id,
                "metadata": result.get('metadata', {}),
                "message": f"Successfully translated to {lang_name}"
            })
        else:
            return jsonify({"success": False, "error": result.get('error', 'Translation failed')}), 500
            
    except Exception as e:
        logger.error(f"Full translation error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# Batch translation for multiple segments
@app.route("/api/translate-batch", methods=["POST"])
@api_login_required
def translate_batch():
    """Translate multiple text segments"""
    data = request.get_json()
    segments = data.get('segments', [])
    target_lang = data.get('target_lang', 'en')
    
    if not segments:
        return jsonify({"success": False, "error": "No segments provided"}), 400
    
    try:
        translated_segments = []
        
        for segment in segments:
            text = segment.get('text', '')
            if text:
                result = translator.translate(text, 'auto', target_lang)
                translated_segments.append({
                    'original': text,
                    'translated': result.get('translated_text', text),
                    'original_lang': result.get('detected_lang', 'unknown')
                })
            else:
                translated_segments.append({
                    'original': '',
                    'translated': '',
                    'original_lang': 'unknown'
                })
        
        return jsonify({
            "success": True,
            "translated_segments": translated_segments,
            "target_lang": target_lang,
            "count": len(translated_segments)
        })
        
    except Exception as e:
        logger.error(f"Batch translation error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ========== TRANSCRIPTION API ==========
@app.route("/api/transcribe", methods=["POST"])
@api_login_required
def transcribe():
    """Handle audio transcription"""
    if 'audio' not in request.files:
        return jsonify({"success": False, "error": "No audio file"}), 400
    
    audio = request.files['audio']
    
    if audio.filename == '':
        return jsonify({"success": False, "error": "No file selected"}), 400
    
    language = request.form.get('language', 'auto')
    audio_data = audio.read()
    filename = secure_filename(audio.filename)
    user_id = session['user_id']
    
    # Save temporarily
    temp_path = get_local_file_path(user_id, filename, 'temp')
    with open(temp_path, 'wb') as f:
        f.write(audio_data)
    
    try:
        language_code = None if language == 'auto' else language
        transcript = asr.transcribe_file(temp_path, language_code=language_code)
        
        # Save audio permanently
        audio_path = get_local_file_path(user_id, filename, 'audio')
        with open(audio_path, 'wb') as f:
            f.write(audio_data)
        
        # Save transcript
        transcript_path = get_local_file_path(user_id, f"{filename.rsplit('.', 1)[0]}.json", 'transcripts')
        with open(transcript_path, 'w', encoding='utf-8') as f:
            json.dump(transcript, f, ensure_ascii=False, indent=2)
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        # Calculate stats
        word_count = transcript['metadata']['total_words']
        speaker_count = transcript['metadata']['speaker_count']
        detected_language = transcript['metadata']['language']
        language_name = transcript['metadata']['language_name']
        
        # Save to database
        db_transcript = Transcript(
            user_id=user_id,
            filename=filename,
            title=filename.rsplit('.', 1)[0].replace('_', ' '),
            duration=transcript['metadata']['duration'],
            word_count=word_count,
            speaker_count=speaker_count,
            file_size=len(audio_data),
            audio_path=audio_path,
            transcript_path=transcript_path,
            transcript_data=transcript
        )
        
        db.session.add(db_transcript)
        db.session.commit()
        index_transcript_safely(db_transcript)
        
        return jsonify({
            "success": True,
            "transcript": transcript,
            "db_id": db_transcript.id,
            "detected_language": detected_language,
            "language_name": language_name,
            "message": f"Transcription completed. Detected language: {language_name}"
        })
        
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/transcripts", methods=["GET"])
@api_login_required
def get_transcripts():
    """Get all transcripts for user"""
    user_id = session['user_id']
    transcripts = Transcript.query.filter_by(user_id=user_id)\
        .order_by(Transcript.created_at.desc()).all()
    
    result = []
    for t in transcripts:
        data = t.to_dict()
        result.append(data)
    
    return jsonify({"success": True, "transcripts": result})

@app.route("/api/transcripts/<int:transcript_id>", methods=["GET"])
@api_login_required
def get_transcript(transcript_id):
    """Get specific transcript"""
    transcript = Transcript.query.get_or_404(transcript_id)
    
    if transcript.user_id != session['user_id']:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    # Update view count
    transcript.view_count += 1
    transcript.last_viewed = datetime.utcnow()
    db.session.commit()
    
    data = transcript.to_dict()
    data['full_data'] = transcript.transcript_data
    data['highlights'] = transcript.highlights or []
    data['notes'] = transcript.notes or []
    data['bookmarks'] = transcript.bookmarks or []
    data['speaker_mapping'] = transcript.speaker_mapping or {}
    
    return jsonify({"success": True, "transcript": data})

@app.route("/api/chat/query", methods=["POST"])
@api_login_required
def chat_query():
    """Answer questions over a user's transcripts using the chat service."""
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    scope = (payload.get("scope") or "all").strip().lower()
    transcript_id = payload.get("transcript_id")
    top_k = payload.get("top_k")

    if scope not in {"all", "current"}:
        return jsonify({"success": False, "error": "Invalid scope"}), 400

    if not question:
        return jsonify({"success": False, "error": "Question is required"}), 400

    try:
        if transcript_id is not None:
            transcript_id = int(transcript_id)
            if "scope" not in payload:
                scope = "current"
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid transcript_id"}), 400

    try:
        if top_k is not None:
            top_k = max(1, min(int(top_k), 10))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid top_k"}), 400

    result = chat_service.answer_question(
        user_id=session["user_id"],
        question=question,
        scope=scope,
        transcript_id=transcript_id,
        top_k=top_k,
    )
    return jsonify(result), (200 if result.get("success") else 400)


@app.route("/api/chat/reindex", methods=["POST"])
@api_login_required
def chat_reindex():
    """Rebuild the current user's Qdrant transcript index."""
    if not rag_index_service.is_available():
        return jsonify({
            "success": False,
            "error": "Qdrant is not configured or the client dependency is missing."
        }), 400

    result = rag_index_service.reindex_user_transcripts(session["user_id"])
    return jsonify({
        "success": True,
        "message": f"Reindexed {result['indexed']} transcripts.",
        **result,
    })

# ========== SUMMARIZATION API ==========
@app.route("/api/summarize", methods=["POST"])
@api_login_required
def summarize():
    data = request.get_json()
    transcript_text = data.get("transcript", "")
    summary_type = data.get("summary_type", "executive")
    length = data.get("length", "medium")
    include_key_points = data.get("include_key_points", True)
    output_language = data.get("output_language", "auto")
    transcript_id = data.get("transcript_id")
    
    if not transcript_text:
        return jsonify({"success": False, "error": "Transcript required"}), 400
    
    try:
        result = summarizer.summarize(
            transcript_text, 
            summary_type, 
            length, 
            include_key_points,
            output_language
        )
        
        if result["success"]:
            summary = Summary(
                user_id=session['user_id'],
                transcript_id=transcript_id,
                title=result.get('title', 'Meeting Summary'),
                content=result['summary'],
                summary_type=summary_type,
                length=length,
                word_count=result['metadata']['word_count'],
                language=result['metadata'].get('output_language', output_language)
            )
            
            db.session.add(summary)
            db.session.commit()
            
            return jsonify({
                "success": True,
                "summary": result["summary"],
                "title": result.get('title'),
                "db_id": summary.id,
                "metadata": result["metadata"]
            })
        else:
            return jsonify({"success": False, "error": result["error"]}), 500
            
    except Exception as e:
        logger.error(f"Summarization error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/summarize-document", methods=["POST"])
@api_login_required
def summarize_document():
    """Handle document upload and summarization"""
    if 'document' not in request.files:
        return jsonify({"success": False, "error": "No document file"}), 400
    
    document = request.files['document']
    
    if document.filename == '':
        return jsonify({"success": False, "error": "No file selected"}), 400
    
    # Save temporarily
    filename = secure_filename(document.filename)
    user_id = session['user_id']
    temp_path = get_local_file_path(user_id, filename, 'temp')
    document.save(temp_path)
    
    try:
        summary_type = request.form.get('type', 'executive')
        length = request.form.get('length', 'medium')
        include_key_points = request.form.get('include_key_points', 'true').lower() == 'true'
        output_language = request.form.get('output_language', 'auto')
        
        result = summarizer.summarize_document(
            temp_path, 
            summary_type, 
            length, 
            output_language
        )
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        if result["success"]:
            # Save to database
            summary = Summary(
                user_id=user_id,
                title=result.get('title', 'Document Summary'),
                content=result['summary'],
                summary_type=summary_type,
                length=length,
                word_count=result['metadata']['word_count'],
                language=result['metadata'].get('output_language', output_language)
            )
            db.session.add(summary)
            db.session.commit()
            
            return jsonify({
                "success": True,
                "summary": result["summary"],
                "metadata": result["metadata"],
                "db_id": summary.id
            })
        else:
            return jsonify({"success": False, "error": result.get("error", "Summarization failed")}), 500
            
    except Exception as e:
        logger.error(f"Document summarization error: {str(e)}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/summaries", methods=["GET"])
@api_login_required
def get_summaries():
    user_id = session['user_id']
    summaries = Summary.query.filter_by(user_id=user_id)\
        .order_by(Summary.created_at.desc()).all()
    
    return jsonify({
        "success": True,
        "summaries": [s.to_dict() for s in summaries]
    })


# ========== TASKS/ACTION ITEMS API ==========

@app.route("/api/tasks", methods=["GET"])
@api_login_required
def get_tasks():
    """Get all tasks for current user"""
    user_id = session['user_id']
    
    tasks = Task.query.filter_by(user_id=user_id)\
        .order_by(
            Task.status.asc(),
            db.case(
                (Task.priority == 'high', 1),
                (Task.priority == 'medium', 2),
                (Task.priority == 'low', 3),
                else_=4
            ),
            Task.created_at.desc()
        ).all()
    
    return jsonify({
        "success": True,
        "tasks": [t.to_dict() for t in tasks]
    })


@app.route("/api/tasks", methods=["POST"])
@api_login_required
def create_task():
    """Create a new task manually"""
    data = request.get_json()
    
    if not data.get('title'):
        return jsonify({"success": False, "error": "Task title is required"}), 400
    
    try:
        task = Task(
            user_id=session['user_id'],
            title=data['title'][:255],
            description=data.get('description'),
            assignee=data.get('assignee', 'Unassigned'),
            priority=data.get('priority', 'medium'),
            status=data.get('status', 'pending'),
            source_text=data.get('source_text'),
            transcript_id=data.get('transcript_id')
        )
        
        if data.get('deadline'):
            try:
                # Try ISO format
                task.deadline = datetime.fromisoformat(data['deadline'].replace('Z', '+00:00'))
            except:
                try:
                    # Try YYYY-MM-DD format
                    task.deadline = datetime.strptime(data['deadline'], '%Y-%m-%d')
                except:
                    pass
        
        db.session.add(task)
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "task": task.to_dict(),
            "message": "Task created successfully"
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating task: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
@api_login_required
def update_task(task_id):
    """Update an existing task"""
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != session['user_id']:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    data = request.get_json()
    
    try:
        if 'title' in data:
            task.title = data['title'][:255]
        if 'description' in data:
            task.description = data['description']
        if 'status' in data:
            task.status = data['status']
            if data['status'] == 'completed' and not task.completed_at:
                task.completed_at = datetime.utcnow()
        if 'assignee' in data:
            task.assignee = data['assignee']
        if 'priority' in data:
            task.priority = data['priority']
        if 'deadline' in data and data['deadline']:
            try:
                task.deadline = datetime.fromisoformat(data['deadline'].replace('Z', '+00:00'))
            except:
                try:
                    task.deadline = datetime.strptime(data['deadline'], '%Y-%m-%d')
                except:
                    pass
        
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "task": task.to_dict(),
            "message": "Task updated successfully"
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating task: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@api_login_required
def delete_task(task_id):
    """Delete a task"""
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != session['user_id']:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    try:
        db.session.delete(task)
        db.session.commit()
        return jsonify({"success": True, "message": "Task deleted successfully"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting task: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/tasks/bulk-delete", methods=["DELETE"])
@api_login_required
def bulk_delete_tasks():
    """Delete all tasks for current user"""
    user_id = session['user_id']
    
    try:
        deleted_count = Task.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return jsonify({
            "success": True, 
            "message": f"Deleted {deleted_count} tasks successfully"
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error bulk deleting tasks: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/tasks/export", methods=["GET"])
@api_login_required
def export_tasks():
    """Export tasks as CSV"""
    user_id = session['user_id']
    
    tasks = Task.query.filter_by(user_id=user_id).all()
    
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Task', 'Assignee', 'Deadline', 'Priority', 'Status', 'Created At', 'Completed At'])
    
    for task in tasks:
        writer.writerow([
            task.id,
            task.title,
            task.assignee or 'Unassigned',
            task.deadline.strftime('%Y-%m-%d') if task.deadline else '',
            task.priority,
            task.status,
            task.created_at.strftime('%Y-%m-%d %H:%M') if task.created_at else '',
            task.completed_at.strftime('%Y-%m-%d %H:%M') if task.completed_at else ''
        ])
    
    output.seek(0)
    
    return send_file(
        BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'tasks_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )


# In app.py - Replace the extract_action_items function

@app.route("/api/extract-action-items", methods=["POST"])
@api_login_required
def extract_action_items():
    """Extract action items from transcript with full language support"""
    data = request.get_json()
    transcript_text = data.get("transcript", "")
    transcript_id = data.get("transcript_id")
    output_language = data.get("output_language", "en")

    if not transcript_text:
        return jsonify({"success": False, "error": "Transcript required"}), 400

    try:
        items = action_extractor.extract(transcript_text, output_language)
        
        if not items:
            return jsonify({
                "success": True,
                "items": [],
                "tasks": [],
                "message": "No action items found in the transcript"
            })
        
        task_list = []
        for item in items:
            deadline = None
            if item.deadline:
                try:
                    deadline = datetime.strptime(item.deadline, '%Y-%m-%d')
                except:
                    try:
                        deadline = datetime.strptime(item.deadline, '%d/%m/%Y')
                    except:
                        pass
            
            task = Task(
                user_id=session['user_id'],
                transcript_id=transcript_id,
                title=item.task[:255],
                assignee=item.assignee or 'Unassigned',
                priority=item.priority or 'medium',
                status='pending',
                source_text=item.source_text[:500] if item.source_text else None,
                deadline=deadline,
                language=output_language
            )
            
            db.session.add(task)
            db.session.flush()
            task_list.append(task.to_dict())
        
        db.session.commit()
        
        # Get language name for display
        lang_names = action_extractor.get_supported_languages()
        lang_name = lang_names.get(output_language, 'English')
        
        return jsonify({
            "success": True,
            "items": [
                {
                    "task": i.task,
                    "assignee": i.assignee,
                    "deadline": i.deadline,
                    "priority": i.priority,
                    "source_text": i.source_text
                }
                for i in items
            ],
            "tasks": task_list,
            "message": f"Extracted {len(items)} action items in {lang_name}"
        })
        
    except Exception as e:
        logger.error(f"Action items extraction error: {str(e)}")
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    

@app.route("/api/tasks/stats", methods=["GET"])
@api_login_required
def get_tasks_stats():
    """Get task statistics for current user"""
    user_id = session['user_id']
    
    tasks = Task.query.filter_by(user_id=user_id).all()
    
    total = len(tasks)
    pending = sum(1 for t in tasks if t.status != 'completed')
    completed = sum(1 for t in tasks if t.status == 'completed')
    
    # Calculate overdue tasks (deadline passed and not completed)
    now = datetime.utcnow()
    overdue = sum(1 for t in tasks if t.status != 'completed' and t.deadline and t.deadline < now)
    
    # Priority breakdown
    high_priority = sum(1 for t in tasks if t.priority == 'high' and t.status != 'completed')
    medium_priority = sum(1 for t in tasks if t.priority == 'medium' and t.status != 'completed')
    low_priority = sum(1 for t in tasks if t.priority == 'low' and t.status != 'completed')
    
    return jsonify({
        "success": True,
        "stats": {
            "total": total,
            "pending": pending,
            "completed": completed,
            "overdue": overdue,
            "high_priority": high_priority,
            "medium_priority": medium_priority,
            "low_priority": low_priority
        }
    })

# ========== SENTIMENT ANALYSIS API ==========
@app.route("/api/sentiment", methods=["POST"])
@api_login_required
def analyze_sentiment():
    data = request.get_json()
    transcript_text = data.get("transcript", "")
    transcript_id = data.get("transcript_id")
    
    if not transcript_text:
        return jsonify({"success": False, "error": "Transcript required"}), 400
    
    try:
        result = sentiment_analyzer.analyze(transcript_text)
        
        sentiment = SentimentAnalysis(
            user_id=session['user_id'],
            transcript_id=transcript_id,
            text_preview=transcript_text[:200],
            sentiment=result['sentiment'],
            polarity_score=result['polarity_score'],
            word_count=len(transcript_text.split())
        )
        
        db.session.add(sentiment)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "result": result,
            "db_id": sentiment.id
        })
        
    except Exception as e:
        logger.error(f"Sentiment analysis error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

# ========== TRANSLATION API ==========
@app.route("/api/translate", methods=["POST"])
@api_login_required
def translate_text():
    data = request.get_json()
    text = data.get("text", "")
    source_lang = data.get("source_lang", "auto")
    target_lang = data.get("target_lang", "es")
    
    if not text:
        return jsonify({"success": False, "error": "No text provided"}), 400
    
    try:
        result = translator.translate(text, source_lang, target_lang)
        
        if result["success"]:
            translation = Translation(
                user_id=session['user_id'],
                source_text=text,
                translated_text=result['translated_text'],
                source_lang=result['source_lang'],
                target_lang=result['target_lang'],
                confidence=result.get('confidence', 0.9),
                word_count=len(text.split())
            )
            
            db.session.add(translation)
            db.session.commit()
            
            return jsonify({
                "success": True,
                "translation": result["translated_text"],
                "db_id": translation.id,
                "confidence": result.get("confidence"),
                "metadata": result.get("metadata", {})
            })
        else:
            return jsonify({"success": False, "error": result["error"]}), 500
            
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/translations", methods=["GET"])
@api_login_required
def get_translations():
    user_id = session['user_id']
    translations = Translation.query.filter_by(user_id=user_id)\
        .order_by(Translation.created_at.desc()).all()
    
    return jsonify({
        "success": True,
        "translations": [t.to_dict() for t in translations]
    })

# ========== DASHBOARD API ==========
@app.route("/api/dashboard/data", methods=["GET"])
@api_login_required
def get_dashboard_data():
    user_id = session['user_id']
    user = get_current_user()
    
    transcript_count = Transcript.query.filter_by(user_id=user_id).count()
    live_session_count = LiveSession.query.filter_by(user_id=user_id).count()
    summary_count = Summary.query.filter_by(user_id=user_id).count()
    task_count = Task.query.filter_by(user_id=user_id).count()
    
    recent_transcripts = Transcript.query.filter_by(user_id=user_id)\
        .order_by(Transcript.created_at.desc()).limit(5).all()
    recent_tasks = Task.query.filter_by(user_id=user_id)\
        .order_by(Task.created_at.desc()).limit(5).all()
    
    pending_tasks = Task.query.filter_by(user_id=user_id, status='pending').count()
    completed_tasks = Task.query.filter_by(user_id=user_id, status='completed').count()
    
    total_duration = 0
    for t in Transcript.query.filter_by(user_id=user_id).all():
        total_duration += t.duration or 0
    
    languages = set()
    for t in Transcript.query.filter_by(user_id=user_id).all():
        if t.transcript_data and 'metadata' in t.transcript_data:
            lang = t.transcript_data['metadata'].get('language', 'en')
            languages.add(lang)
    
    user_name = user.full_name if user and user.full_name else (user.username if user else 'User')
    
    return jsonify({
        "success": True,
        "user_name": user_name,
        "stats": {
            "transcripts": transcript_count,
            "live_sessions": live_session_count,
            "summaries": summary_count,
            "tasks": task_count,
            "pending_tasks": pending_tasks,
            "completed_tasks": completed_tasks,
            "total_duration": total_duration,
            "total_hours": round(total_duration / 3600, 1),
            "languages_used": len(languages)
        },
        "recent": {
            "transcripts": [t.to_dict() for t in recent_transcripts],
            "tasks": [t.to_dict() for t in recent_tasks]
        }
    })

# ========== YOUTUBE PROCESSING API ==========

@app.route("/api/youtube/info", methods=["POST"])
@api_login_required
def get_youtube_info():
    """Get YouTube video information"""
    data = request.get_json()
    url = data.get('url', '')
    
    if not url:
        return jsonify({"success": False, "error": "URL required"}), 400
    
    result = youtube_processor.get_video_info(url)
    
    if result['success']:
        return jsonify({
            "success": True,
            "info": {
                "title": result['title'],
                "duration": result['duration'],
                "uploader": result['uploader'],
                "views": result['views'],
                "thumbnail": result['thumbnail']
            }
        })
    else:
        return jsonify({"success": False, "error": result['error']}), 400

@app.route("/api/youtube/process", methods=["POST"])
@api_login_required
def process_youtube():
    """Process YouTube URL and transcribe"""
    data = request.get_json()
    url = data.get('url', '')
    language = data.get('language', 'auto')
    
    if not url:
        return jsonify({"success": False, "error": "URL required"}), 400
    
    temp_audio_path = None
    
    try:
        logger.info(f"Processing YouTube URL: {url}")
        
        result = youtube_processor.extract_transcript_from_url(url)
        
        if not result['success']:
            return jsonify({"success": False, "error": result['error']}), 400
        
        if 'transcript' in result:
            transcript = result['transcript']
            detected_language = transcript['metadata']['language']
            language_name = transcript['metadata']['language_name']
            
            user_id = session['user_id']
            
            db_transcript = Transcript(
                user_id=user_id,
                filename=f"youtube_{result['video_id']}.json",
                title=result['title'][:100],
                duration=transcript['metadata'].get('duration', 0),
                word_count=transcript['metadata']['total_words'],
                speaker_count=transcript['metadata']['speaker_count'],
                file_size=0,
                audio_path=None,
                transcript_path=None,
                transcript_data=transcript,
                source_url=url
            )
            
            db.session.add(db_transcript)
            db.session.commit()
            index_transcript_safely(db_transcript)
            
            return jsonify({
                "success": True,
                "transcript": transcript,
                "db_id": db_transcript.id,
                "title": result['title'],
                "duration": result['duration'],
                "uploader": result['uploader'],
                "thumbnail": result['thumbnail'],
                "detected_language": detected_language,
                "language_name": language_name,
                "message": f"YouTube video transcribed successfully!"
            })
        
        temp_audio_path = result['audio_path']
        
        language_code = None if language == 'auto' else language
        transcript = asr.transcribe_file(temp_audio_path, language_code=language_code)
        
        user_id = session['user_id']
        audio_filename = f"youtube_{result['video_id']}_{result['title'][:50].replace(' ', '_')}.wav"
        audio_path = get_local_file_path(user_id, audio_filename, 'audio')
        
        import shutil
        shutil.copy2(temp_audio_path, audio_path)
        
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
        
        transcript_filename = f"youtube_{result['video_id']}.json"
        transcript_path = get_local_file_path(user_id, transcript_filename, 'transcripts')
        with open(transcript_path, 'w', encoding='utf-8') as f:
            json.dump(transcript, f, ensure_ascii=False, indent=2)
        
        db_transcript = Transcript(
            user_id=user_id,
            filename=audio_filename,
            title=result['title'][:100],
            duration=transcript['metadata']['duration'],
            word_count=transcript['metadata']['total_words'],
            speaker_count=transcript['metadata']['speaker_count'],
            file_size=os.path.getsize(audio_path),
            audio_path=audio_path,
            transcript_path=transcript_path,
            transcript_data=transcript,
            source_url=url
        )
        
        db.session.add(db_transcript)
        db.session.commit()
        index_transcript_safely(db_transcript)
        
        return jsonify({
            "success": True,
            "transcript": transcript,
            "db_id": db_transcript.id,
            "title": result['title'],
            "duration": result['duration'],
            "uploader": result['uploader'],
            "thumbnail": result['thumbnail'],
            "detected_language": transcript['metadata']['language'],
            "language_name": transcript['metadata']['language_name'],
            "message": f"YouTube video processed successfully!"
        })
        
    except Exception as e:
        logger.error(f"YouTube processing error: {str(e)}")
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except:
                pass
        return jsonify({"success": False, "error": str(e)}), 500

# ========== TEXT-TO-SPEECH API ==========
@app.route("/api/tts", methods=["POST"])
@api_login_required
def text_to_speech():
    """Convert text to speech for listening"""
    data = request.get_json()
    text = data.get('text', '')
    language = data.get('language', 'en')
    
    if not text:
        return jsonify({"success": False, "error": "Text required"}), 400
    
    try:
        audio_data = generate_speech(text, language)
        
        return send_file(
            BytesIO(audio_data),
            mimetype='audio/mpeg',
            as_attachment=False,
            download_name='speech.mp3'
        )
    except Exception as e:
        logger.error(f"TTS error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

def generate_speech(text, language='en'):
    """Generate speech using multiple fallback engines"""
    try:
        from gtts import gTTS
        import io
        
        lang_map = {
            'hi': 'hi', 'mr': 'mr', 'ta': 'ta', 'te': 'te', 'bn': 'bn',
            'gu': 'gu', 'kn': 'kn', 'ml': 'ml', 'pa': 'pa', 'en': 'en',
            'es': 'es', 'fr': 'fr', 'de': 'de', 'ja': 'ja', 'zh': 'zh'
        }
        
        tts_lang = lang_map.get(language, 'en')
        
        chunks = [text[i:i+500] for i in range(0, len(text), 500)]
        
        audio_parts = []
        for chunk in chunks:
            tts = gTTS(text=chunk, lang=tts_lang, slow=False)
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_parts.append(audio_buffer.getvalue())
        
        from pydub import AudioSegment
        combined = AudioSegment.empty()
        for part in audio_parts:
            audio = AudioSegment.from_mp3(io.BytesIO(part))
            combined += audio
        
        output = io.BytesIO()
        combined.export(output, format='mp3')
        return output.getvalue()
        
    except Exception as e:
        logger.error(f"gTTS failed: {str(e)}")
        raise Exception("TTS failed. Using browser speech synthesis as fallback.")

# ========== FOLDERS API ==========
@app.route("/api/folders", methods=["GET", "POST"])
@api_login_required
def manage_folders():
    user_id = session['user_id']
    
    if request.method == 'GET':
        folders = TranscriptFolder.query.filter_by(user_id=user_id, parent_id=None).all()
        return jsonify({
            "success": True,
            "folders": [{"id": f.id, "name": f.name, "color": f.color} for f in folders]
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        folder = TranscriptFolder(
            user_id=user_id,
            name=data['name'],
            color=data.get('color', 'gray')
        )
        db.session.add(folder)
        db.session.commit()
        return jsonify({"success": True, "folder": {"id": folder.id, "name": folder.name}})

@app.route("/api/folders/<int:folder_id>", methods=["PUT", "DELETE"])
@api_login_required
def update_folder(folder_id):
    folder = TranscriptFolder.query.get_or_404(folder_id)
    if folder.user_id != session['user_id']:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    if request.method == 'PUT':
        data = request.get_json()
        if 'name' in data:
            folder.name = data['name']
        if 'color' in data:
            folder.color = data['color']
        db.session.commit()
        return jsonify({"success": True})
    
    elif request.method == 'DELETE':
        db.session.delete(folder)
        db.session.commit()
        return jsonify({"success": True})

# ========== HEALTH CHECK ==========
@app.route("/api/health", methods=["GET"])
def health_check():
    try:
        db.session.execute('SELECT 1')
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return jsonify({
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat()
    })

# ========== ERROR HANDLERS ==========
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"success": False, "error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({"success": False, "error": "Internal server error"}), 500

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        logger.info("Database tables created/verified")
    
    app.run(debug=True, host='0.0.0.0', port=5000)

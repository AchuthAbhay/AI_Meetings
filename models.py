# models.py
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100))
    job_title = db.Column(db.String(100))
    department = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    transcripts = db.relationship('Transcript', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    summaries = db.relationship('Summary', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    translations = db.relationship('Translation', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    events = db.relationship('CalendarEvent', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    settings = db.relationship('UserSettings', backref='user', uselist=False, cascade='all, delete-orphan')
    live_sessions = db.relationship('LiveSession', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    sentiment_analyses = db.relationship('SentimentAnalysis', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name or self.username,
            'job_title': self.job_title,
            'department': self.department,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class UserSettings(db.Model):
    __tablename__ = 'user_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    email_notifications = db.Column(db.Boolean, default=True)
    desktop_notifications = db.Column(db.Boolean, default=True)
    theme = db.Column(db.String(20), default='dark')
    sidebar_collapsed = db.Column(db.Boolean, default=False)
    
    security_level = db.Column(db.String(20), default='standard')
    security_pin = db.Column(db.String(10), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Transcript(db.Model):
    __tablename__ = 'transcripts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(255))
    duration = db.Column(db.Float)
    word_count = db.Column(db.Integer)
    speaker_count = db.Column(db.Integer)
    file_size = db.Column(db.Integer)
    
    # Local storage paths
    audio_path = db.Column(db.String(500))
    transcript_path = db.Column(db.String(500))
    
    # Store transcript data in DB for quick access
    transcript_data = db.Column(db.JSON)
    
    # Enhanced features fields
    highlights = db.Column(db.JSON, default=list)
    notes = db.Column(db.JSON, default=list)
    bookmarks = db.Column(db.JSON, default=list)
    speaker_mapping = db.Column(db.JSON, default=dict)
    tags = db.Column(db.JSON, default=list)
    folder_id = db.Column(db.Integer, db.ForeignKey('transcript_folders.id'), nullable=True)
    is_favorite = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)
    last_viewed = db.Column(db.DateTime)
    source_url = db.Column(db.String(500), nullable=True)  # For YouTube links
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'title': self.title or self.filename,
            'duration': self.duration,
            'word_count': self.word_count,
            'speaker_count': self.speaker_count,
            'file_size': self.file_size,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'language': self.transcript_data.get('metadata', {}).get('language', 'en') if self.transcript_data else 'en',
            'language_name': self.transcript_data.get('metadata', {}).get('language_name', 'English') if self.transcript_data else 'English',
            'is_favorite': self.is_favorite,
            'tags': self.tags or [],
            'source_url': self.source_url
        }

class TranscriptFolder(db.Model):
    __tablename__ = 'transcript_folders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('transcript_folders.id'), nullable=True)
    color = db.Column(db.String(20), default='gray')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    transcripts = db.relationship('Transcript', backref='folder', lazy='dynamic')
    children = db.relationship('TranscriptFolder', backref='parent', remote_side=[id])

class Summary(db.Model):
    __tablename__ = 'summaries'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    transcript_id = db.Column(db.Integer, db.ForeignKey('transcripts.id'), nullable=True)
    title = db.Column(db.String(255))
    content = db.Column(db.Text, nullable=False)
    summary_type = db.Column(db.String(50))
    length = db.Column(db.String(20))
    word_count = db.Column(db.Integer)
    language = db.Column(db.String(20), default='en')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title or 'Untitled Summary',
            'content': self.content[:200] + '...' if len(self.content) > 200 else self.content,
            'type': self.summary_type,
            'word_count': self.word_count,
            'language': self.language or 'en',
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    transcript_id = db.Column(db.Integer, db.ForeignKey('transcripts.id'), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    assignee = db.Column(db.String(100))
    deadline = db.Column(db.DateTime)
    priority = db.Column(db.String(20), default='medium')
    status = db.Column(db.String(20), default='pending')
    source_text = db.Column(db.Text, nullable=True)
    language = db.Column(db.String(20), default='en')  # ADD THIS LINE
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'assignee': self.assignee or 'Unassigned',
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'priority': self.priority,
            'status': self.status,
            'source_text': self.source_text[:200] if self.source_text else None,
            'language': self.language or 'en',  # ADD THIS LINE
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

class Translation(db.Model):
    __tablename__ = 'translations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    transcript_id = db.Column(db.Integer, db.ForeignKey('transcripts.id'), nullable=True)
    source_text = db.Column(db.Text, nullable=False)
    translated_text = db.Column(db.Text, nullable=False)
    source_lang = db.Column(db.String(10))
    target_lang = db.Column(db.String(10))
    confidence = db.Column(db.Float)
    word_count = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'source_text': self.source_text[:100] + '...' if len(self.source_text) > 100 else self.source_text,
            'translated_text': self.translated_text[:100] + '...' if len(self.translated_text) > 100 else self.translated_text,
            'source_lang': self.source_lang,
            'target_lang': self.target_lang,
            'confidence': self.confidence,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class CalendarEvent(db.Model):
    __tablename__ = 'calendar_events'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    event_date = db.Column(db.DateTime, nullable=False)
    event_type = db.Column(db.String(50), default='meeting')
    reminder = db.Column(db.Boolean, default=False)
    reminder_time = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'event_type': self.event_type,
            'reminder': self.reminder
        }

class SentimentAnalysis(db.Model):
    __tablename__ = 'sentiment_analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    transcript_id = db.Column(db.Integer, db.ForeignKey('transcripts.id'), nullable=True)
    text_preview = db.Column(db.String(500))
    sentiment = db.Column(db.String(20))
    polarity_score = db.Column(db.Float)
    word_count = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'sentiment': self.sentiment,
            'polarity_score': self.polarity_score,
            'word_count': self.word_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class LiveSession(db.Model):
    __tablename__ = 'live_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_name = db.Column(db.String(255), nullable=False, default='Live Recording')
    status = db.Column(db.String(20), default='active')
    duration = db.Column(db.Integer, default=0)
    word_count = db.Column(db.Integer, default=0)
    speaker_count = db.Column(db.Integer, default=0)
    detected_language = db.Column(db.String(50), default='auto')
    transcript_data = db.Column(db.JSON, default=list)
    audio_path = db.Column(db.String(500), nullable=True)  # Add this field
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_name': self.session_name,
            'status': self.status,
            'duration': self.duration,
            'word_count': self.word_count,
            'speaker_count': self.speaker_count,
            'detected_language': self.detected_language,
            'transcript_preview': self.transcript_data[-5:] if self.transcript_data else [],
            'transcript_full': self.transcript_data,
            'audio_url': f'/api/audio/{self.id}' if self.audio_path else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None
        }
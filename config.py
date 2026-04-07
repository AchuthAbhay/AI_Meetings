# config.py
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Base directory
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database
    instance_path = os.path.join(BASE_DIR, 'instance')
    os.makedirs(instance_path, exist_ok=True)
    db_path = os.path.join(instance_path, 'insightflow.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_PERMANENT = True
    
    # Upload folder
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024
    
    # ========== API KEYS ==========
    ASSEMBLYAI_API_KEY = os.environ.get('ASSEMBLYAI_API_KEY', '')
    SARVAM_API_KEY = os.environ.get('SARVAM_API_KEY', '')
    GOOGLE_GEMINI_API_KEY = os.environ.get('GOOGLE_GEMINI_API_KEY', '')
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
    
    # Language configuration
    SUPPORTED_LANGUAGES = {
        'auto': 'Auto-detect',
        'en': 'English',
        'hi': 'Hindi',
        'mr': 'Marathi',
        'ta': 'Tamil',
        'te': 'Telugu',
        'bn': 'Bengali',
        'gu': 'Gujarati',
        'kn': 'Kannada',
        'ml': 'Malayalam',
        'pa': 'Punjabi',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'ja': 'Japanese',
        'zh': 'Chinese'
    }
    
    # Indian languages specifically
    INDIAN_LANGUAGES = {
        'hi': 'Hindi',
        'mr': 'Marathi',
        'ta': 'Tamil',
        'te': 'Telugu',
        'bn': 'Bengali',
        'gu': 'Gujarati',
        'kn': 'Kannada',
        'ml': 'Malayalam',
        'pa': 'Punjabi'
    }
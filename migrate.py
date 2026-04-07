# migrate.py
#!/usr/bin/env python3
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from extensions import db
from models import *

def ensure_instance_dir():
    instance_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    db_file = os.path.join(instance_dir, 'insightflow.db')
    if not os.path.exists(db_file):
        open(db_file, 'w').close()
        print(f"✅ Created database file: {db_file}")
    return instance_dir

def init_db():
    with app.app_context():
        ensure_instance_dir()
        print(f"📊 Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        print("🗑️  Dropping all tables...")
        db.drop_all()
        print("✅ Dropped all existing tables")
        
        print("✨ Creating all tables...")
        db.create_all()
        print("✅ Created all tables")
        
        # Create admin user
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@insightflow.com',
                full_name='Admin User',
                job_title='System Administrator',
                department='IT'
            )
            admin.set_password('password123')
            db.session.add(admin)
            db.session.flush()
            print("✅ Created admin user")
        
        # Create user settings for admin
        settings = UserSettings.query.filter_by(user_id=admin.id).first()
        if not settings:
            settings = UserSettings(
                user_id=admin.id,
                email_notifications=True,
                desktop_notifications=True,
                theme='dark',
                sidebar_collapsed=False
            )
            db.session.add(settings)
            print("✅ Created user settings")
        
        db.session.commit()
        
        print("\n" + "="*50)
        print("✅ Database initialized successfully!")
        print("="*50)
        print(f"📊 Database location: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print("👤 Admin user: admin@insightflow.com / password123")
        print("="*50)

def add_sample_data():
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("❌ Admin user not found. Run without --sample first.")
            return
        
        print("📝 Adding sample data...")
        
        # Check if sample data already exists
        if Transcript.query.filter_by(user_id=admin.id).first():
            print("⚠️  Sample data already exists. Skipping.")
            return
        
        # Sample transcript with Hindi and English mixed (Hinglish)
        sample_transcript_data = {
            'segments': [
                {'speaker': 'Raj', 'text': "Namaste sabko. Aaj hum Q4 ke goals discuss karenge.", 'start': 0, 'end': 5000},
                {'speaker': 'Priya', 'text': "I think we should focus on increasing market share by 20% in the next quarter.", 'start': 5000, 'end': 12000},
                {'speaker': 'Raj', 'text': "Good point. Budget allocation kya rahega iske liye?", 'start': 12000, 'end': 18000},
                {'speaker': 'Amit', 'text': "Humne approximately ₹50 lakh budget allocate kiya hai marketing ke liye.", 'start': 18000, 'end': 25000},
                {'speaker': 'Priya', 'text': "Let's schedule a follow-up meeting with the finance team next Monday.", 'start': 25000, 'end': 32000},
                {'speaker': 'Raj', 'text': "Agreed. Aur action items bana lete hain sabke liye.", 'start': 32000, 'end': 38000}
            ],
            'metadata': {
                'duration': 38,
                'total_words': 85,
                'speaker_count': 3,
                'language': 'hi',
                'language_name': 'Hindi'
            }
        }
        
        transcript = Transcript(
            user_id=admin.id,
            filename='sample_meeting.mp3',
            title='Q4 Planning Meeting - Hindi+English',
            duration=38,
            word_count=85,
            speaker_count=3,
            file_size=1024 * 1024,
            audio_path='uploads/1/audio/sample_audio.mp3',
            transcript_path='uploads/1/transcripts/sample_transcript.json',
            transcript_data=sample_transcript_data
        )
        db.session.add(transcript)
        db.session.flush()
        print("✅ Added sample transcript")
        
        # Sample summary in Hindi
        summary = Summary(
            user_id=admin.id,
            transcript_id=transcript.id,
            title='Q4 Planning Meeting Summary',
            content='Team discussed Q4 goals focusing on market share increase of 20%. Key decisions include ₹50 lakh budget allocation for marketing. Action items: Schedule follow-up with finance team.',
            summary_type='executive',
            length='medium',
            word_count=28,
            language='hi'
        )
        db.session.add(summary)
        print("✅ Added sample summary")
        
        # Sample tasks
        tasks = [
            Task(
                user_id=admin.id,
                transcript_id=transcript.id,
                title='Prepare Q4 budget report',
                assignee='John Smith',
                deadline=datetime.now() + timedelta(days=7),
                priority='high',
                status='pending'
            ),
            Task(
                user_id=admin.id,
                transcript_id=transcript.id,
                title='Schedule finance meeting',
                assignee='Sarah Johnson',
                deadline=datetime.now() + timedelta(days=3),
                priority='medium',
                status='pending'
            )
        ]
        db.session.add_all(tasks)
        print("✅ Added sample tasks")
        
        db.session.commit()
        print("\n✅ Sample data added successfully!")

def add_language_column():
    """Add language column to summaries table if not exists"""
    with app.app_context():
        try:
            # Check if column exists by trying to query it
            db.session.execute('SELECT language FROM summaries LIMIT 1')
            print("✅ Language column already exists")
        except:
            try:
                # Add the column using raw SQL
                db.session.execute('ALTER TABLE summaries ADD COLUMN language VARCHAR(20) DEFAULT "en"')
                db.session.commit()
                print("✅ Added language column to summaries table")
            except Exception as e:
                print(f"⚠️  Could not add column: {e}")

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🔧 Database Migration Tool")
    print("="*50)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--sample':
            add_sample_data()
        elif sys.argv[1] == '--add-language':
            add_language_column()
        else:
            print("Usage: python migrate.py [--sample] [--add-language]")
    else:
        init_db()
        print("\n💡 Run with --sample to add test data: python migrate.py --sample")
        print("💡 Run with --add-language to add language column: python migrate.py --add-language")
# modules/youtube_processor.py

import os
import re
import yt_dlp
import logging
from pydub import AudioSegment
import tempfile
from datetime import datetime

logger = logging.getLogger(__name__)

class YouTubeProcessor:
    """Process YouTube videos and extract audio for transcription"""
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        logger.info("YouTubeProcessor initialized")
    
    def extract_audio_from_url(self, url, output_path=None):
        """
        Extract audio from YouTube URL and save as WAV file
        
        Args:
            url: YouTube URL or any video URL
            output_path: Path to save audio file (optional)
        
        Returns:
            dict: Contains file path, title, duration, etc.
        """
        try:
            # Validate URL
            if not self._is_valid_url(url):
                raise ValueError("Invalid URL")
            
            # Create temp file path
            if not output_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = os.path.join(self.temp_dir, f'youtube_audio_{timestamp}.wav')
            
            # yt-dlp options for best audio quality
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }],
                'outtmpl': output_path.replace('.wav', ''),
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Unknown Title')
                duration = info.get('duration', 0)
                
                # Download and convert
                logger.info(f"Downloading audio from: {title}")
                ydl.download([url])
                
                # Find the downloaded file
                base_path = output_path.replace('.wav', '')
                actual_path = None
                for ext in ['.wav', '.mp3', '.m4a']:
                    test_path = base_path + ext
                    if os.path.exists(test_path):
                        actual_path = test_path
                        break
                
                if not actual_path:
                    raise Exception("Downloaded file not found")
                
                # Convert to WAV if needed
                if not actual_path.endswith('.wav'):
                    audio = AudioSegment.from_file(actual_path)
                    audio.export(output_path, format='wav')
                    os.remove(actual_path)
                    actual_path = output_path
                
                logger.info(f"Audio extracted successfully: {actual_path}")
                
                return {
                    'success': True,
                    'audio_path': actual_path,
                    'title': title,
                    'duration': duration,
                    'url': url
                }
                
        except Exception as e:
            logger.error(f"YouTube extraction failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _is_valid_url(self, url):
        """Check if URL is valid"""
        youtube_patterns = [
            r'(youtube\.com\/watch\?v=)',
            r'(youtu\.be\/)',
            r'(youtube\.com\/shorts\/)',
        ]
        
        for pattern in youtube_patterns:
            if re.search(pattern, url):
                return True
        
        # Also accept direct audio/video URLs
        if re.search(r'\.(mp3|wav|m4a|mp4)$', url):
            return True
            
        return False
    
    def get_video_info(self, url):
        """Get video information without downloading"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'success': True,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'views': info.get('view_count', 0),
                    'thumbnail': info.get('thumbnail', '')
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}
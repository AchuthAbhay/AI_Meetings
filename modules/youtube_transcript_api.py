# modules/youtube_transcript_api.py
import re
import requests
import logging

logger = logging.getLogger(__name__)

class YouTubeTranscriptAPI:
    """Extract YouTube subtitles directly - NO FFMPEG, NO API KEY required"""
    
    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        logger.info("YouTubeTranscriptAPI initialized (No FFmpeg mode)")
    
    def extract_transcript(self, url):
        """Extract transcript directly from YouTube's subtitle API"""
        try:
            video_id = self._extract_video_id(url)
            if not video_id:
                return {"success": False, "error": "Invalid YouTube URL"}
            
            video_info = self._get_video_info(video_id)
            
            # Try multiple languages
            languages = ['hi', 'mr', 'ta', 'te', 'bn', 'gu', 'kn', 'ml', 'pa', 'en']
            
            for lang in languages:
                try:
                    subtitle_url = f"https://www.youtube.com/api/timedtext?v={video_id}&lang={lang}&fmt=json3"
                    response = requests.get(subtitle_url, timeout=15, headers={'User-Agent': self.user_agent})
                    
                    if response.status_code == 200 and response.text:
                        data = response.json()
                        segments = self._parse_captions(data)
                        if segments and len(segments) > 0:
                            return {
                                "success": True,
                                "segments": segments,
                                "language": lang,
                                "title": video_info.get('title', 'YouTube Video'),
                                "duration": video_info.get('duration', 0),
                                "thumbnail": video_info.get('thumbnail', '')
                            }
                except Exception as e:
                    continue
            
            return {"success": False, "error": "No subtitles available for this video"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _extract_video_id(self, url):
        patterns = [
            r'(?:youtube\.com\/watch\?v=)([^&]+)',
            r'(?:youtu\.be\/)([^?]+)',
            r'(?:youtube\.com\/shorts\/)([^?]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def _parse_captions(self, data):
        segments = []
        if 'events' in data:
            for i, event in enumerate(data['events'][:100]):
                if 'segs' in event and event['segs']:
                    text = ' '.join(seg.get('utf8', '') for seg in event['segs'])
                    if text.strip():
                        start = event.get('tStartMs', i * 3000)
                        end = start + event.get('dDurationMs', 3000)
                        segments.append({
                            "speaker": f"Speaker {chr(65 + (i % 26))}",
                            "text": text.strip(),
                            "start": start,
                            "end": end
                        })
        return segments
    
    def _get_video_info(self, video_id):
        try:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            response = requests.get(oembed_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {
                    "title": data.get('title', 'YouTube Video'),
                    "uploader": data.get('author_name', 'Unknown'),
                    "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                    "duration": 0
                }
        except:
            pass
        return {
            "title": "YouTube Video",
            "uploader": "Unknown",
            "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            "duration": 0
        }
    
    def get_video_info_only(self, url):
        video_id = self._extract_video_id(url)
        if not video_id:
            return {"success": False, "error": "Invalid URL"}
        info = self._get_video_info(video_id)
        return {
            "success": True,
            "title": info['title'],
            "uploader": info['uploader'],
            "thumbnail": info['thumbnail']
        }
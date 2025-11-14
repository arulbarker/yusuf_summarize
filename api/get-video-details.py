from http.server import BaseHTTPRequestHandler
import json
import os
import yt_dlp
import urllib.request
from openai import OpenAI

# Initialize DeepSeek client
# IMPORTANT: Set DEEPSEEK_API_KEY in Vercel environment variables!
deepseek_key = os.getenv("DEEPSEEK_API_KEY")
if not deepseek_key:
    print("WARNING: DEEPSEEK_API_KEY not found in environment variables!")
    print("Please set it in Vercel Dashboard → Settings → Environment Variables")

client = OpenAI(
    api_key=deepseek_key,
    base_url="https://api.deepseek.com"
)

SYSTEM_PROMPT = """
You are an advanced AI that summarizes content in a structured format.
Your goal is to extract the main topic and provide key bullet points.

### Guidelines:
- **Extract the main topic/title** of the content.
- **List key points** under the topic in a clear and informative way.
- If the content covers **multiple topics**, create separate sections for each.
- Keep the summary **concise, to the point, and informative**.

### Example Output:
**Topic:** Artificial Intelligence in Healthcare
- **Definition:** AI is used to improve diagnostics and treatment.
- **Applications:**
  - AI-powered diagnostic tools detect diseases early.
  - AI chatbots assist in patient interactions.
- **Challenges:**
  - Data privacy concerns.
  - High implementation costs.

---
"""

def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def groupTranscript(transcript, interval):
    grouped = []
    current_group = {"start": None, "text": ""}
    group_start = 0

    for entry in transcript:
        start_time = entry["start"]
        text = entry["text"]

        if current_group["start"] is None:
            current_group["start"] = start_time
            group_start = start_time

        if start_time < group_start + interval:
            current_group["text"] += (" " if current_group["text"] else "") + text
        else:
            grouped.append(current_group)
            current_group = {
                "start": start_time,
                "text": text
            }
            group_start = start_time

    if current_group["text"]:
        grouped.append(current_group)

    return grouped

def sumTranscript(transcript):
    try:
        if not deepseek_key:
            return "Error: DEEPSEEK_API_KEY not configured. Please set it in Vercel environment variables."

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"**Text to Summarize:**\n{transcript}\n\n**Output:**"}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        error_msg = str(e)
        if "authentication" in error_msg.lower() or "401" in error_msg:
            return "Error: Invalid DeepSeek API key. Please check your DEEPSEEK_API_KEY in Vercel environment variables."
        return f"Error generating summary: {error_msg}"

def getVideoDetails(video_url):
    try:
        # Extract video ID from URL
        if "v=" in video_url:
            video_id = video_url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in video_url:
            video_id = video_url.split("youtu.be/")[1].split("?")[0]
        else:
            return {"error": "Invalid YouTube URL"}

        # Configure yt-dlp options with anti-bot bypass
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'id', 'es', 'fr', 'de', 'pt', 'ja', 'ko'],
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            # Anti-bot configuration
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage', 'configs'],
                }
            },
            # Simulate real browser headers
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            }
        }

        # Fetch video info and subtitles using yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(video_url, download=False)
            except Exception as e:
                error_str = str(e)
                if "age" in error_str.lower():
                    return {"error": "This video is age-restricted and cannot be accessed. Please try a different video."}
                elif "private" in error_str.lower():
                    return {"error": "This video is private or unavailable. Please try a different video."}
                elif "unavailable" in error_str.lower():
                    return {"error": "This video is unavailable. It may have been deleted or is region-locked."}
                else:
                    return {"error": f"Unable to access video: {error_str[:200]}"}

            # Get video title
            title = info.get('title', f'YouTube Video {video_id}')

            # Get subtitles
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})
            all_subs = {**automatic_captions, **subtitles}

            if not all_subs:
                return {"error": "This video does not have subtitles/captions available. Please try another video with subtitles enabled."}

            # Find best available subtitle language
            target_lang = None
            preferred_langs = ['en', 'id', 'es', 'fr', 'de', 'pt', 'ja', 'ko']

            for lang in preferred_langs:
                if lang in all_subs:
                    target_lang = lang
                    break

            if not target_lang:
                # Use first available language
                target_lang = list(all_subs.keys())[0]

            subtitle_formats = all_subs[target_lang]

            # Find json3 format (best for parsing)
            json3_url = None
            for fmt in subtitle_formats:
                if fmt.get('ext') == 'json3':
                    json3_url = fmt.get('url')
                    break

            if not json3_url:
                return {"error": "Unable to extract subtitle data. Please try a different video."}

            # Download and parse subtitle data
            try:
                with urllib.request.urlopen(json3_url) as response:
                    subtitle_data = json.loads(response.read().decode('utf-8'))
            except Exception as e:
                return {"error": f"Failed to download subtitles: {str(e)[:200]}"}

            # Parse events (subtitle entries)
            events = subtitle_data.get('events', [])
            transcript = []

            for event in events:
                if 'segs' in event:
                    start = event.get('tStartMs', 0) / 1000.0
                    text = ''.join([seg.get('utf8', '') for seg in event['segs']])
                    if text.strip():
                        transcript.append({
                            'start': start,
                            'text': text.strip()
                        })

            if not transcript or len(transcript) == 0:
                return {"error": "No subtitle content found. Please try a different video."}

        # Group transcript by 30-second intervals
        grouped_transcript = groupTranscript(transcript, 30)

        formatted_transcript = []
        transcript_text_parts = []

        for entry in grouped_transcript:
            transcript_text_parts.append(entry["text"])
            formatted_transcript.append({
                "timestamp": format_timestamp(entry["start"]),
                "text": entry["text"]
            })

        transcript_text = " ".join(transcript_text_parts)

        return {
            "title": title,
            "transcript_text": transcript_text,
            "formatted_transcript": formatted_transcript
        }
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)[:300]}"}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        response = {"message": "YouTube Summary API is working with yt-dlp!"}
        self.wfile.write(json.dumps(response).encode())
        return

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            video_url = data.get("video_url")

            if not video_url:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing video_url"}).encode())
                return

            result = getVideoDetails(video_url)

            if "error" in result:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": result["error"]}).encode())
                return

            title = result["title"]
            transcript_text = result["transcript_text"]
            formatted_transcript = result["formatted_transcript"]

            summary = sumTranscript(transcript_text)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            response = {
                "title": title,
                "transcript": formatted_transcript,
                "summary": summary
            }
            self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

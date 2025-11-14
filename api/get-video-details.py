from http.server import BaseHTTPRequestHandler
import json
import os
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI

# Initialize DeepSeek client
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY", "sk-36fca51fd07e4382a5d6e627955613ed"),
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
        return f"Error generating summary: {str(e)}"

def getVideoDetails(video_url):
    try:
        # Extract video ID from URL
        if "v=" in video_url:
            video_id = video_url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in video_url:
            video_id = video_url.split("youtu.be/")[1].split("?")[0]
        else:
            return {"error": "Invalid YouTube URL"}

        # Get transcript with robust error handling
        transcript = None
        error_messages = []

        # Method 1: Try simple method first (most reliable)
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception as e1:
            error_messages.append(f"Simple method failed: {type(e1).__name__}")

            # Method 2: Try to list and fetch manually
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

                # Try English first
                try:
                    trans_obj = transcript_list.find_transcript(['en'])
                    transcript = trans_obj.fetch()
                except:
                    # Try Indonesian and other common languages
                    try:
                        trans_obj = transcript_list.find_transcript(['id', 'es', 'fr', 'de', 'pt', 'ja', 'ko'])
                        transcript = trans_obj.fetch()
                    except:
                        # Try ANY available transcript
                        for trans_obj in transcript_list:
                            try:
                                transcript = trans_obj.fetch()
                                break  # Success, exit loop
                            except Exception as fetch_err:
                                error_messages.append(f"Fetch {trans_obj.language_code} failed: {type(fetch_err).__name__}")
                                continue

            except Exception as e2:
                error_messages.append(f"List method failed: {type(e2).__name__}")

        # Check result
        if transcript is None or len(transcript) == 0:
            # Provide detailed error message
            if "ParseError" in str(error_messages):
                return {"error": "YouTube is temporarily blocking transcript requests. Please try again in a few minutes or try a different video."}
            elif "NoTranscript" in str(error_messages):
                return {"error": "This video does not have subtitles/captions available. Please try another video with subtitles enabled."}
            else:
                return {"error": f"Unable to retrieve video transcript. YouTube may be rate limiting requests. Please try again later."}

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

        # Get video title from first transcript entry or use a default
        title = f"YouTube Video {video_id}"

        return {
            "title": title,
            "transcript_text": transcript_text,
            "formatted_transcript": formatted_transcript
        }
    except Exception as e:
        return {"error": str(e)}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        response = {"message": "YouTube Summary API is working!"}
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

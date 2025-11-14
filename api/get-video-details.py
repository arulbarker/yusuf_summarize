from http.server import BaseHTTPRequestHandler
import json
import os
import time
from youtube_transcript_api import YouTubeTranscriptApi
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

        # Get transcript with robust error handling and retry mechanism
        transcript = None
        error_messages = []
        max_retries = 2  # Reduced to avoid Vercel timeout

        for attempt in range(max_retries):
            try:
                # Add small delay between retries
                if attempt > 0:
                    time.sleep(1.5)  # Keep delays short for Vercel
                    error_messages.append(f"Retry {attempt + 1}/{max_retries}")

                # Method 1: Try simple get_transcript (fastest)
                try:
                    transcript = YouTubeTranscriptApi.get_transcript(video_id)
                    if transcript and len(transcript) > 0:
                        error_messages.append(f"Success via simple method")
                        break  # Success!
                except Exception as e1:
                    error_messages.append(f"Simple: {type(e1).__name__}")

                # Small delay before next method
                time.sleep(0.5)

                # Method 2: Try list_transcripts and get first available
                try:
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

                    # Try to get any available transcript
                    available_transcripts = list(transcript_list)

                    if not available_transcripts:
                        error_messages.append("No transcripts available")
                        continue

                    # Try each available transcript (max 3 to avoid timeout)
                    for idx, trans_obj in enumerate(available_transcripts[:3]):
                        try:
                            if idx > 0:
                                time.sleep(0.3)  # Small delay between fetches
                            transcript = trans_obj.fetch()
                            if transcript and len(transcript) > 0:
                                error_messages.append(f"Success: {trans_obj.language_code}")
                                break  # Success!
                        except Exception as fetch_err:
                            error_messages.append(f"{trans_obj.language_code}: {type(fetch_err).__name__}")
                            continue

                    if transcript and len(transcript) > 0:
                        break  # Success!

                except Exception as e2:
                    error_messages.append(f"List: {type(e2).__name__}")

            except Exception as retry_err:
                error_messages.append(f"Attempt {attempt + 1} failed: {type(retry_err).__name__}")

            # If we have a transcript, break the retry loop
            if transcript and len(transcript) > 0:
                break

        # Check result after all retries
        if transcript is None or len(transcript) == 0:
            # Provide detailed error message
            error_str = str(error_messages)
            if "ParseError" in error_str:
                return {"error": "YouTube is temporarily blocking transcript requests. This video may have restricted access. Please try: 1) Wait a few minutes and try again, 2) Try a different video, or 3) Check if the video has subtitles enabled."}
            elif "NoTranscript" in error_str or "No transcripts available" in error_str:
                return {"error": "This video does not have subtitles/captions available. Please try another video with subtitles enabled."}
            else:
                return {"error": f"Unable to retrieve video transcript after {max_retries} attempts. YouTube may be rate limiting requests. Please try again later or use a different video."}

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

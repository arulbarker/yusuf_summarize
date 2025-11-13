from flask import Flask, request, jsonify
import os
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI
import sys

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

app = Flask(__name__)

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

        # Get transcript
        fetched_transcript = YouTubeTranscriptApi().fetch(video_id, languages=['en'])
        transcript = fetched_transcript.to_raw_data()
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

@app.route('/api/get-video-details', methods=['POST', 'GET'])
def handler(request):
    if request.method == 'GET':
        return jsonify({"message": "YouTube Summary API is working!"})

    try:
        data = request.get_json()
        video_url = data.get("video_url")

        if not video_url:
            return jsonify({"error": "Missing video_url"}), 400

        result = getVideoDetails(video_url)

        if "error" in result:
            return jsonify({"error": result["error"]}), 500

        title = result["title"]
        transcript_text = result["transcript_text"]
        formatted_transcript = result["formatted_transcript"]

        summary = sumTranscript(transcript_text)

        return jsonify({
            "title": title,
            "transcript": formatted_transcript,
            "summary": summary
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

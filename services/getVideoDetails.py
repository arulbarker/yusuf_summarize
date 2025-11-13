import os;
import requests;
from youtube_transcript_api import YouTubeTranscriptApi;
from dotenv import load_dotenv;
from utils import format_timestamp,groupTranscript

load_dotenv();


# https://www.googleapis.com/youtube/v3/videos?part=snippet&id=dQw4w9WgXcQ&key=API_KEY
def getTitle(video_id):
    api_key = os.getenv("GOOGLE_API_KEY");
    url = "https://www.googleapis.com/youtube/v3/videos";
    params = {
        "part": "snippet",
        "id": video_id,
        "key": api_key
    };

    try:
        response = requests.get(url, params=params);
        data = response.json();

        if "items" in data and len(data["items"]) > 0:
            return data["items"][0]["snippet"]["title"];
        else:
            return "Unknown Title";
    except Exception as e:
        return { "error": str(e) };
    

def getVideoDetails(video_url):
    try:
        video_id = video_url.split("v=")[1];

        # Get transcript - try multiple methods WITHOUT translation to avoid rate limits
        transcript = None

        try:
            # Get transcript list
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Try to find English transcript first
            try:
                transcript = transcript_list.find_transcript(['en']).fetch()
            except:
                # If no English, get ANY available transcript (DeepSeek supports multiple languages)
                try:
                    # Try common languages first
                    transcript = transcript_list.find_transcript(['id', 'es', 'fr', 'de', 'pt', 'ja', 'ko', 'zh-Hans', 'zh-Hant']).fetch()
                except:
                    # Get first available transcript without translation
                    try:
                        for available_transcript in transcript_list:
                            transcript = available_transcript.fetch()
                            break
                    except:
                        pass

        except:
            # Fallback: try simple method
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id)
            except:
                pass

        if transcript is None:
            return {"error": "This video does not have subtitles/captions available. Please try another video with subtitles enabled."}

        grouped_transcript = groupTranscript(transcript,30);

        formatted_transcript = [];
        transcript_text_parts = [];

        for entry in grouped_transcript:
            transcript_text_parts.append(entry["text"]);
            formatted_transcript.append({
                "timestamp": format_timestamp(entry["start"]),
                "text": entry["text"]
            });

        transcript_text = " ".join(transcript_text_parts);
        title = getTitle(video_id);

        if "error" in title:
            return {"error": title["error"]};
    
        return {
            "title": title,
            "transcript_text": transcript_text,
            "formatted_transcript": formatted_transcript
        };
    except Exception as e:
        return { "error": str(e) };

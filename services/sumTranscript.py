from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()

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



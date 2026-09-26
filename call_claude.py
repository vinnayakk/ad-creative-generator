from dotenv import load_dotenv
from anthropic import Anthropic
from pydantic import BaseModel

load_dotenv()


class AdHeadlines(BaseModel):
    headlines: list[str]


client = Anthropic()

response = client.messages.parse(
    model="claude-sonnet-5",
    max_tokens=500,
    messages=[
        {"role": "user", "content": "Write 5 short ad headlines for a productivity app called TaskFlow."}
    ],
    output_format=AdHeadlines,
)

ads = response.parsed_output   # already a validated AdHeadlines instance

for i, headline in enumerate(ads.headlines, start=1):
    print(f"{i}. {headline}")
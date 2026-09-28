import base64

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI()  # reads OPENAI_API_KEY automatically, same pattern as Anthropic()

result = client.images.edit(
    model="gpt-image-1.5",
    image=open("product.png", "rb"),
    prompt=(
        "Place this product on a clean marble countertop with soft morning "
        "light, minimal styling, shot like a premium ad campaign photo."
    ),
    size="1024x1024",
)

image_bytes = base64.b64decode(result.data[0].b64_json)

with open("ad_image.png", "wb") as f:
    f.write(image_bytes)

print("Saved ad_image.png")
import base64
import json

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

PRODUCT_IMAGE_PATH = "product.png"


def generate_image(brief: dict, variant: dict) -> str:
    """
    Generate one ad image from a brand brief and one copy variant.

    Args:
        brief: a loaded brand-brief dict (same shape as erbology-hemp-seed-oil.json)
        variant: a dict with at least 'headline' and 'variant_number' keys

    Returns:
        The file path of the saved PNG.
    """
    client = OpenAI()

    brand = brief["brand"]
    tone = brief["tone"]

    prompt = (
        f"Keep the product, styling, and composition from the input image as unchanged "
        f"as possible. Only adjust background, lighting, or setting to fit this ad "
        f"headline: \"{variant['headline']}\". "
        f"Brand: {brand['name']}, personality: {', '.join(brand['personality'])}. "
        f"Voice/style cues: {', '.join(tone['voice_words'])}. "
        f"Avoid: {', '.join(tone['we_are_not'])}."
    )

    result = client.images.edit(
        model="gpt-image-1.5",
        image=open(PRODUCT_IMAGE_PATH, "rb"),
        prompt=prompt,
        size="1024x1024",
        input_fidelity="high",
    )

    image_bytes = base64.b64decode(result.data[0].b64_json)

    safe_brand = brand["name"].lower().replace(" ", "_")
    output_path = f"{safe_brand}_variant_{variant['variant_number']}.png"

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    return output_path


# if __name__ == "__main__":
#     with open("erbology-hemp-seed-oil.json") as f:
#         brief = json.load(f)

#     variant = {
#         "variant_number": 1,
#         "headline": "Paid before the harvest, not after",
#         "cta": "Start your first bag free",
#     }

#     saved_path = generate_image(brief, variant)
#     print(f"Saved {saved_path}")
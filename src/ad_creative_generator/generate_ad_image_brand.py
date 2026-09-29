import base64
import json

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def generate_image(brief: dict, variant: dict, product_image_path: str) -> str:
    """
    Generate one ad image from a brand brief and one copy variant.

    Args:
        brief: a loaded brand-brief dict
        variant: a dict with at least 'headline' and 'variant_number' keys
        product_image_path: path to this brand's base product photo

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
        f"Avoid: {', '.join(tone['we_are_not'])}. "
        f"If you render any text onto the image, match the exact typeface, weight, and "
        f"letterform style already visible on the product's own label or packaging in "
        f"the reference image. Do not introduce a different or generic font — in "
        f"particular, never default to a plain serif like Times New Roman when no such "
        f"font appears on the actual packaging."
    )

    result = client.images.edit(
        model="gpt-image-2",
        image=open(product_image_path, "rb"),
        prompt=prompt,
        size="1024x1024",
        quality="high",
    )

    image_bytes = base64.b64decode(result.data[0].b64_json)

    safe_brand = brand["name"].lower().replace(" ", "_")
    output_path = f"{safe_brand}_variant_{variant['variant_number']}.png"

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    return output_path
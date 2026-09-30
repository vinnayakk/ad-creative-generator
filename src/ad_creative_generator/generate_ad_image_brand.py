import base64
from pathlib import Path

from openai import OpenAI


def generate_image(
    client: OpenAI, brief: dict, variant: dict, product_image_path: str, output_dir: Path
) -> str:
    """
    Generate one ad image from a brand brief and one copy variant.

    Args:
        client: an OpenAI client, already constructed with an API key
        brief: a loaded brand-brief dict
        variant: a dict with at least 'headline' and 'variant_number' keys
        product_image_path: path to this brand's base product photo
        output_dir: directory to save the generated PNG into — must already
            exist and be unique per run (the caller's job), so two concurrent
            runs never write to the same path

    Returns:
        The file path of the saved PNG.
    """
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
        f"letterform style used for the brand's own name/logotype as printed on the "
        f"product (for {brand['name']}, that's the \"{brand['name']}\" wordmark itself) — "
        f"not other type on the label, which may use a different typeface for a tagline, "
        f"category name, or fine print. Use that one typeface, and only that one, for any "
        f"text you add, consistently across every image."
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
    output_path = Path(output_dir) / f"{safe_brand}_variant_{variant['variant_number']}.png"

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    return str(output_path)
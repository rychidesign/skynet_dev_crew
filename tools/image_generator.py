import os
import httpx
import replicate
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ImageGeneratorInput(BaseModel):
    prompt: str = Field(
        description=(
            "Detailed image generation prompt. Use the base template from "
            "specs/visual-style.md if available. Be specific about style, "
            "colors, composition, and mood."
        )
    )
    filename: str = Field(
        description=(
            "Output filename with .webp extension, e.g. 'hero-banner.webp'. "
            "Use kebab-case. File will be saved to output/public/images/<filename>."
        )
    )
    aspect_ratio: str = Field(
        default="16:9",
        description=(
            "Image aspect ratio. Options: '16:9' (hero/banner), '1:1' (avatar/icon), "
            "'4:3' (feature illustration), '3:2' (general). Default: '16:9'."
        )
    )


class ImageGeneratorTool(BaseTool):
    name: str = "image_generator"
    description: str = (
        "Generate an image via Replicate FLUX.2 API and save it to output/public/images/. "
        "Provide THREE arguments:\n"
        "  prompt: detailed generation prompt (read specs/visual-style.md first)\n"
        "  filename: output filename with .webp extension (e.g. 'hero-banner.webp')\n"
        "  aspect_ratio: '16:9' for banners, '1:1' for avatars, '4:3' for illustrations\n"
        "Returns saved file path on success, error message on failure."
    )
    args_schema: Type[BaseModel] = ImageGeneratorInput

    project_path: Optional[str] = None

    def _run(self, prompt: str, filename: str, aspect_ratio: str = "16:9") -> str:
        try:
            output = replicate.run(
                "black-forest-labs/flux-dev",
                input={
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "output_format": "webp",
                    "output_quality": 90,
                    "num_inference_steps": 28,
                }
            )

            image_url = str(output[0]) if isinstance(output, list) else str(output)

            images_dir = os.path.join(self.project_path or ".", "public", "images")
            os.makedirs(images_dir, exist_ok=True)
            filepath = os.path.join(images_dir, filename)

            with httpx.Client(timeout=60.0) as client:
                response = client.get(image_url)
                response.raise_for_status()
                with open(filepath, "wb") as f:
                    f.write(response.content)

            size = os.path.getsize(filepath)
            return f"✅ Image saved: {filepath} ({size:,} bytes)"

        except Exception as e:
            return f"❌ Image generation failed: {e}"


def create_image_generator(project_path: str = "") -> ImageGeneratorTool:
    """Factory that creates an ImageGeneratorTool bound to a specific output directory."""
    return ImageGeneratorTool(project_path=project_path)

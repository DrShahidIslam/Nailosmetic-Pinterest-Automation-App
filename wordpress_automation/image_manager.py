import requests
import os
import time
from PIL import Image

class ImageManager:
    def __init__(self, siliconflow_api_key: str):
        self.api_key = siliconflow_api_key
        self.api_url = "https://api.siliconflow.cn/v1/images/generations"
        # We'll use the same model as in the root main.py for consistency
        self.model = "Kwai-Kolors/Kolors"

    def convert_to_webp(self, image_path: str) -> str:
        """
        Convert an image to WebP format for SEO optimization.
        """
        output_path = image_path.rsplit(".", 1)[0] + ".webp"
        with Image.open(image_path) as img:
            img.save(output_path, "WEBP", quality=85)
        return output_path

    def generate_image(self, prompt: str, aspect_ratio: str = "4:5", output_path: str = "image.png") -> str:
        """
        Generate an image using SiliconFlow.
        :param prompt: The prompt for generation
        :param aspect_ratio: "16:9" for featured, "4:5" for blocks
        """
        # SiliconFlow's Kolors supports specific sizes. 
        # For 4:5 vertical: 768x960 or similar.
        # For 16:9 horizontal: 1024x576.
        if aspect_ratio == "16:9":
            size = "1024x576"
        else: # 4:5 default for blocks as requested
            size = "768x1024" # Close enough to 4:5 vertical (3:4 actually)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "prompt": prompt + ", professional macro commercial photography of a manicure, focus on nail art details, high definition, aesthetic beauty photography, luxury editorial vibe, sharp focus, vibrant colors, soft lighting",
            "negative_prompt": "mutated hands, poorly drawn hands, extra fingers, missing fingers, malformed hands, deformed fingers, blurry, worst quality, low quality, watermark, text",
            "image_size": size,
            "batch_size": 1,
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(self.api_url, headers=headers, json=payload, timeout=120)
                if response.status_code == 200:
                    result = response.json()
                    image_url = result["images"][0]["url"]
                    
                    # Download
                    img_data = requests.get(image_url, timeout=60).content
                    with open(output_path, "wb") as f:
                        f.write(img_data)
                    return output_path
                else:
                    print(f"SiliconFlow Error ({response.status_code}): {response.text}")
                    time.sleep(10)
            except Exception as e:
                print(f"SiliconFlow Exception: {e}")
                time.sleep(10)

        raise Exception("Failed to generate image after retries.")

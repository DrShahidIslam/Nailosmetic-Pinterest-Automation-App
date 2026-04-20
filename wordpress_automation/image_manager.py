import requests
import os
import time
import random
from PIL import Image
from huggingface_hub import InferenceClient
from typing import Dict, Any, List, Optional

class ImageManager:
    def __init__(self, hf_api_keys: List[str] = None, siliconflow_api_key: str = None):
        """
        Initialize the ImageManager with multi-key support for Hugging Face.
        """
        self.hf_api_keys = hf_api_keys or []
        self.silicon_key = siliconflow_api_key
        self.silicon_url = "https://api.siliconflow.cn/v1/images/generations"
        self.silicon_model = "Kwai-Kolors/Kolors"

    def convert_to_webp(self, image_path: str) -> str:
        """
        Convert an image to WebP format for SEO optimization.
        """
        output_path = image_path.rsplit(".", 1)[0] + ".webp"
        with Image.open(image_path) as img:
            img.save(output_path, "WEBP", quality=85)
        return output_path

    def generate_image(self, prompt: str, aspect_ratio: str = "4:5", output_path: str = "image.png", prefer_kolors: bool = False) -> str:
        """
        The 'Brilliant' Orchestrator with customizable priority.
        If prefer_kolors=True (WP Bot): Kolors -> Flux -> Pollinations
        If prefer_kolors=False (Pinterest Bot): Flux -> Kolors -> Pollinations
        """
        enhanced_prompt = prompt + ", high quality, ultra realistic, masterpiece, aesthetic 4k"
        model_id = "black-forest-labs/FLUX.1-schnell"

        # Plan A for WordPress (Elite Bot) - Priority Kolors
        if prefer_kolors and self.silicon_key:
            try:
                print("   🎨 Attempting SiliconFlow (Kolors) - WP Priority...")
                size_sf = "768x1024" if aspect_ratio == "4:5" else "1024x1024"
                return self._generate_siliconflow(prompt, size_sf, output_path)
            except Exception as e:
                print(f"   ⚠️ SiliconFlow failed, trying Flux: {str(e)[:50]}")

        # Plan A for Pinterest (or Fallback for WP) - Flux Cycling
        if self.hf_api_keys:
            try:
                print(f"   🎨 Attempting FLUX with {len(self.hf_api_keys)} keys...")
                return self._generate_priority_flux(prompt, output_path)
            except Exception as e:
                print(f"   ⚠️ Flux cycling failed: {str(e)[:50]}")

        # Plan B for Pinterest (Fallback) - Kolors
        if not prefer_kolors and self.silicon_key:
            try:
                print("   🎨 Attempting SiliconFlow (Kolors) - Fallback...")
                size_sf = "768x1024" if aspect_ratio == "4:5" else "1024x1024"
                return self._generate_siliconflow(prompt, size_sf, output_path)
            except Exception as e:
                print(f"   ⚠️ SiliconFlow fallback failed: {str(e)[:50]}")

        # 3. Last Resort: Pollinations (Zero-cost, Unlimited)
        print("   🎨 Attempting Pollinations (Zero-cost Fallback)...")
        return self._generate_pollinations(prompt, aspect_ratio, output_path)

    def _generate_siliconflow(self, prompt: str, size: str, output_path: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.silicon_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.silicon_model,
            "prompt": prompt + ", professional photography, studio lighting",
            "negative_prompt": "blurry, low quality, watermark, text",
            "image_size": size,
            "batch_size": 1,
        }
        resp = requests.post(self.silicon_url, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            url = resp.json()["images"][0]["url"]
            img_data = requests.get(url, timeout=60).content
            with open(output_path, "wb") as f:
                f.write(img_data)
            return output_path
        raise Exception(f"SiliconFlow Failed: {resp.status_code}")

    def _generate_pollinations(self, prompt: str, aspect_ratio: str, output_path: str) -> str:
        w, h = (1024, 768) if aspect_ratio == "16:9" else (768, 1024)
        seed = random.randint(0, 999999)
        import urllib.parse
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width={w}&height={h}&model=flux&nologo=true&seed={seed}"
        resp = requests.get(url, timeout=60)
        if resp.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(resp.content)
            return output_path
        raise Exception(f"Pollinations Failed: {resp.status_code}")

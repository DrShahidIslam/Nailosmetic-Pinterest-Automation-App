import requests
import os
import time
import random
from PIL import Image

class ImageManager:
    def __init__(self, hf_api_key: str = None, siliconflow_api_key: str = None):
        self.hf_api_key = hf_api_key
        self.silicon_key = siliconflow_api_key
        self.hf_url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
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

    def _generate_huggingface(self, prompt: str, output_path: str) -> str:
        if not self.hf_api_key:
            raise Exception("Hugging Face key missing")
        
        headers = {"Authorization": f"Bearer {self.hf_api_key}"}
        payload = {
            "inputs": prompt + ", high quality, ultra realistic, masterpiece, aesthetic 4k",
            "parameters": {"num_inference_steps": 4}
        }
        
        for _ in range(3):
            resp = requests.post(self.hf_url, headers=headers, json=payload, timeout=60)
            if resp.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(resp.content)
                return output_path
            elif resp.status_code == 503:
                time.sleep(20)
            else:
                break
        raise Exception(f"HF Failed: {resp.status_code}")

    def _generate_siliconflow(self, prompt: str, size: str, output_path: str) -> str:
        if not self.silicon_key:
            raise Exception("SiliconFlow key missing")
        
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
        # 16:9 -> 1024x576, else 768x1024
        w, h = (1024, 576) if aspect_ratio == "16:9" else (768, 1024)
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

    def generate_image(self, prompt: str, aspect_ratio: str = "4:5", output_path: str = "image.png") -> str:
        """
        Generate an image using available backends with fallback logic.
        """
        size = "1024x576" if aspect_ratio == "16:9" else "768x1024"
        
        # 1. Hugging Face
        try:
            return self._generate_huggingface(prompt, output_path)
        except Exception as e:
            print(f"⚠️ HF Fallback: {e}")

        # 2. SiliconFlow
        try:
            return self._generate_siliconflow(prompt, size, output_path)
        except Exception as e:
            print(f"⚠️ SiliconFlow Fallback: {e}")

        # 3. Pollinations
        try:
            return self._generate_pollinations(prompt, aspect_ratio, output_path)
        except Exception as e:
            print(f"❌ All image generation failed: {e}")
            raise e

import requests
import os
import time
import random
from PIL import Image
from huggingface_hub import InferenceClient
from typing import Dict, Any, List, Optional

class ImageManager:
    def __init__(self, hf_api_keys: List[str] = None, siliconflow_api_key: str = None, cloudflare_account_id: str = None, cloudflare_api_token: str = None):
        """
        Initialize the ImageManager with support for Hugging Face, Cloudflare Workers AI, and SiliconFlow.
        """
        self.hf_api_keys = hf_api_keys or []
        self.silicon_key = siliconflow_api_key or os.getenv("SILICONFLOW_API_KEY")
        self.silicon_url = "https://api.siliconflow.cn/v1/images/generations"
        self.silicon_model = "Kwai-Kolors/Kolors"

        self.cf_account_id = cloudflare_account_id or os.getenv("CLOUDFLARE_ACCOUNT_ID")
        self.cf_api_token = cloudflare_api_token or os.getenv("CLOUDFLARE_API_TOKEN")

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
        Universal priority chain:
        1. Hugging Face FLUX (1st Priority)
        2. SiliconFlow Kolors (2nd Priority)
        3. Cloudflare Workers AI SDXL (3rd Priority)
        4. Pollinations (4th Priority)
        """
        # 1st Priority: Hugging Face FLUX cycling
        if self.hf_api_keys:
            try:
                print(f"   🎨 Attempting FLUX with {len(self.hf_api_keys)} keys...")
                return self._generate_priority_flux(prompt, aspect_ratio, output_path)
            except Exception as e:
                print(f"   ⚠️ Flux cycling failed: {str(e)[:50]}")

        # 2nd Priority: SiliconFlow Kolors
        if self.silicon_key:
            try:
                print("   🎨 Attempting SiliconFlow (Kolors)...")
                if aspect_ratio == "16:9":
                    size_sf = "1024x768"
                elif aspect_ratio == "9:16":
                    size_sf = "768x1024"
                else: # 4:5
                    size_sf = "768x1024"
                return self._generate_siliconflow(prompt, size_sf, output_path)
            except Exception as e:
                print(f"   ⚠️ SiliconFlow failed: {str(e)[:50]}")

        # 3rd Priority: Cloudflare Workers AI SDXL
        if self.cf_account_id and self.cf_api_token:
            try:
                print("   🎨 Attempting Cloudflare Workers AI (SDXL)...")
                return self._generate_cloudflare(prompt, aspect_ratio, output_path)
            except Exception as e:
                print(f"   ⚠️ Cloudflare SDXL failed: {str(e)[:50]}")

        # 4th Priority: Pollinations (Zero-cost fallback)
        print("   🎨 Attempting Pollinations (Zero-cost Fallback)...")
        return self._generate_pollinations(prompt, aspect_ratio, output_path)

    def _generate_priority_flux(self, prompt: str, aspect_ratio: str, output_path: str) -> str:
        """
        Cycles through available HF API keys to generate an image via FLUX.1-schnell.
        """
        from huggingface_hub import InferenceClient
        
        # Determine width and height based on aspect ratio
        if aspect_ratio == "16:9":
            w, h = 1024, 576
        elif aspect_ratio == "9:16":
            w, h = 768, 1344
        else: # Default 4:5
            w, h = 800, 1000
            
        errors = []
        for i, key in enumerate(self.hf_api_keys):
            try:
                client = InferenceClient(api_key=key)
                image = client.text_to_image(
                    prompt,
                    model="black-forest-labs/FLUX.1-schnell",
                    width=w,
                    height=h
                )
                image.save(output_path)
                print(f"    Success with HF Key {i+1}/{len(self.hf_api_keys)} ({w}x{h})")
                return output_path
            except Exception as e:
                errors.append(f"Key {i+1} failed: {str(e)[:50]}")
        
        raise Exception(f"All Flux keys failed: {'; '.join(errors)}")

    def _generate_cloudflare(self, prompt: str, aspect_ratio: str, output_path: str) -> str:
        url = f"https://api.cloudflare.com/client/v4/accounts/{self.cf_account_id}/ai/run/@cf/stabilityai/stable-diffusion-xl-base-1.0"
        headers = {
            "Authorization": f"Bearer {self.cf_api_token}",
            "Content-Type": "application/json",
        }
        
        # Determine width and height based on aspect ratio
        if aspect_ratio == "16:9":
            w, h = 1024, 576
            enhanced_prompt = prompt + ", highly detailed, masterpiece, best quality, horizontal landscape, 16:9 aspect ratio, high resolution, photorealistic"
        elif aspect_ratio == "9:16":
            w, h = 768, 1344
            enhanced_prompt = prompt + ", highly detailed, masterpiece, best quality, vertical portrait, 9:16 aspect ratio, high resolution, photorealistic"
        else: # Default 4:5
            w, h = 800, 1000
            enhanced_prompt = prompt + ", highly detailed, masterpiece, best quality, vertical portrait, 4:5 aspect ratio, high resolution, photorealistic"
            
        payload = {
            "prompt": enhanced_prompt,
            "width": w,
            "height": h
        }
        
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(resp.content)
            return output_path
            
        raise Exception(f"Cloudflare SDXL Failed: {resp.status_code} - {resp.text}")

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
        if aspect_ratio == "16:9":
            w, h = 1024, 576
        elif aspect_ratio == "9:16":
            w, h = 768, 1344
        else: # Default 4:5
            w, h = 800, 1000
            
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

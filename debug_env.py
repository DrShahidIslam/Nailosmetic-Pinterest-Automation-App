import os
from dotenv import load_dotenv

load_dotenv()
print(f"GEMINI_API_KEYS: {'SET' if os.getenv('GEMINI_API_KEYS') else 'MISSING'}")
print(f"HUGGINGFACE_API_KEY: {'SET' if os.getenv('HUGGINGFACE_API_KEY') else 'MISSING'}")
print(f"SILICONFLOW_API_KEY: {'SET' if os.getenv('SILICONFLOW_API_KEY') else 'MISSING'}")
print(f"PINTEREST_ACCESS_TOKEN: {'SET' if os.getenv('PINTEREST_ACCESS_TOKEN') else 'MISSING'}")

import os
import urllib.parse
import base64
import requests
from dotenv import load_dotenv

def main():
    load_dotenv()
    app_id = os.getenv("PINTEREST_APP_ID", "").strip("'").strip('"')
    app_secret = os.getenv("PINTEREST_APP_SECRET", "").strip("'").strip('"')
    redirect_uri = "https://localhost/"

    scopes = "boards:read,boards:write,pins:read,pins:write,user_accounts:read"

    url = f"https://www.pinterest.com/oauth/?client_id={app_id}&redirect_uri={urllib.parse.quote(redirect_uri)}&response_type=code&scope={scopes}"
    print(f"========================================")
    print(f"1. Go to this URL in your browser:\n\n{url}\n")
    print("2. Authorize the app, then you will be redirected to localhost (it will say 'Unable to connect' - that's fine).")
    print("3. Look at the URL in your address bar. It will look like: https://localhost/?code=abc123def456...")
    print("4. Copy ONLY the code part (abc123def456...).")
    print(f"========================================")
    
    import sys
    if len(sys.argv) > 1:
        code = sys.argv[1].strip()
    else:
        code = input("\nEnter the authorization code: ").strip()
    
    if not code:
        print("No code entered. Exiting.")
        return
        
    credentials = base64.b64encode(f"{app_id}:{app_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    }
    
    response = requests.post("https://api.pinterest.com/v5/oauth/token", headers=headers, data=data)
    if response.status_code == 200:
        tokens = response.json()
        print("\n[SUCCESS] New tokens acquired.")
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        
        # update .env
        with open(".env", "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        with open(".env", "w", encoding="utf-8") as f:
            for line in lines:
                if line.startswith("PINTEREST_ACCESS_TOKEN="):
                    f.write(f"PINTEREST_ACCESS_TOKEN='{access_token}'\n")
                elif line.startswith("PINTEREST_REFRESH_TOKEN="):
                    f.write(f"PINTEREST_REFRESH_TOKEN='{refresh_token}'\n")
                else:
                    f.write(line)
                    
        print("[SAVED] Updated .env with new access and refresh tokens. You can now run refresh_and_analyze.py without errors!")
    else:
        print(f"[ERROR] Failed to exchange code: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    main()

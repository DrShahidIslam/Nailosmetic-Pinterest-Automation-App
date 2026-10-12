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
                    
        print("[SAVED] Updated local .env with new access and refresh tokens.")

        # Attempt to update GitHub Secrets automatically
        gh_pat = os.getenv("GH_PAT", "").strip()
        if gh_pat:
            import subprocess
            try:
                env = os.environ.copy()
                env["GH_TOKEN"] = gh_pat
                subprocess.run(["gh", "secret", "set", "PINTEREST_ACCESS_TOKEN", "--body", access_token], env=env, check=True)
                subprocess.run(["gh", "secret", "set", "PINTEREST_REFRESH_TOKEN", "--body", refresh_token], env=env, check=True)
                print("🔒 [SAVED] Successfully updated GitHub Secrets: PINTEREST_ACCESS_TOKEN and PINTEREST_REFRESH_TOKEN!")
            except Exception as e:
                print(f"\n⚠️ Could not automatically update GitHub Secrets via gh CLI ({e}).")
                print("👉 Please manually update GitHub Repository Secrets:")
                print(f"   • PINTEREST_ACCESS_TOKEN = {access_token[:20]}...")
                print(f"   • PINTEREST_REFRESH_TOKEN = {refresh_token[:20]}...")
        else:
            print("\n👉 Please remember to update GitHub Secrets (Settings > Secrets and variables > Actions):")
            print(f"   • PINTEREST_ACCESS_TOKEN")
            print(f"   • PINTEREST_REFRESH_TOKEN")
    else:
        print(f"[ERROR] Failed to exchange code: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    main()

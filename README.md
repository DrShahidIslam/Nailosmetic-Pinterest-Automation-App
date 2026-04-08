# 🌸 Nailosmetic Pinterest Automation Bot

A fully automated Pinterest bot that generates and publishes **one vertical (9:16) nail art pin per day** using AI-generated content and images. Designed to run for free via **GitHub Actions**.

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    GitHub Actions (Cron)                      │
│                  Runs daily at 14:00 UTC                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Phase 1: 🧠 THE BRAIN (Gemini API)                         │
│  → Generates title, description & image prompt               │
│                         ↓                                    │
│  Phase 2: 🎨 THE ARTIST (SiliconFlow / FLUX.1-schnell)      │
│  → Generates a vertical 9:16 nail art image                  │
│                         ↓                                    │
│  Phase 3: ✨ THE DESIGNER (Pillow)                           │
│  → Adds gradient overlay + title text to the image           │
│                         ↓                                    │
│  Phase 4: 📌 THE PUBLISHER (Pinterest REST API)              │
│  → Publishes the pin to your Pinterest board                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 📋 Prerequisites

- Python 3.10+
- A Google account (for Gemini API)
- A SiliconFlow account (for image generation)
- A Pinterest **Business** account (for the API)
- A GitHub account (for hosting & automation)

---

## 🔑 Step 1: Get Your API Keys

### 1.1 — Google Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Click **"Create API Key"**
3. Select or create a Google Cloud project
4. Copy the API key — this is your `GEMINI_API_KEY`

> 💡 The Gemini API has a generous free tier (15 RPM for Gemini 2.0 Flash).

### 1.2 — SiliconFlow API Key

1. Go to [SiliconFlow](https://siliconflow.cn/) and create a free account
2. Navigate to **API Keys** in your dashboard
3. Click **"Create New API Key"**
4. Copy the key — this is your `SILICONFLOW_API_KEY`

> 💡 SiliconFlow offers free credits for FLUX.1-schnell image generation.

### 1.3 — Pinterest API Keys (Most Complex — Follow Carefully!)

#### Step A: Create a Pinterest Business Account

1. Go to [pinterest.com](https://www.pinterest.com/)
2. If you have a personal account, go to **Settings → Account Management → Convert to Business Account**
3. If you don't have one, sign up at [business.pinterest.com](https://business.pinterest.com/)

#### Step B: Create a Pinterest Developer App

1. Go to [Pinterest Developers](https://developers.pinterest.com/)
2. Log in with your **Business** account
3. Click **"My Apps"** in the top navigation
4. Click **"Connect App"**
5. Fill out the application form:
   - **App Name:** `Nailosmetic Bot` (or any name you want)
   - **Description:** `Automated nail art pin publisher`
   - **Website URL:** `https://nailosmetic.com`
   - **Redirect URI:** `https://localhost/` (we'll use this for the OAuth flow)
6. Submit the app. It will start in **Trial Access** mode — this is fine for personal use!
7. Once created, note down your:
   - **App ID** → This is your `PINTEREST_APP_ID`
   - **App Secret** → This is your `PINTEREST_APP_SECRET`

#### Step C: Get Your Access Token & Refresh Token

1. Open this URL in your browser (replace `YOUR_APP_ID` with your actual App ID):

```
https://www.pinterest.com/oauth/?client_id=YOUR_APP_ID&redirect_uri=https://localhost/&response_type=code&scope=boards:read,pins:read,pins:write,boards:write&state=nailosmetic
```

2. Log in and click **"Allow"** to authorize the app
3. You'll be redirected to a URL like:
   ```
   https://localhost/?code=AUTHORIZATION_CODE&state=nailosmetic
   ```
4. Copy the `AUTHORIZATION_CODE` from the URL

5. Now exchange this code for tokens. Open a terminal and run:

```bash
curl -X POST https://api.pinterest.com/v5/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Authorization: Basic $(echo -n 'YOUR_APP_ID:YOUR_APP_SECRET' | base64)" \
  -d "grant_type=authorization_code" \
  -d "code=AUTHORIZATION_CODE" \
  -d "redirect_uri=https://localhost/"
```

> **On Windows (PowerShell)?** Use this instead:
> ```powershell
> $credentials = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("YOUR_APP_ID:YOUR_APP_SECRET"))
> 
> $headers = @{
>     "Content-Type" = "application/x-www-form-urlencoded"
>     "Authorization" = "Basic $credentials"
> }
> 
> $body = "grant_type=authorization_code&code=AUTHORIZATION_CODE&redirect_uri=https://localhost/"
> 
> Invoke-RestMethod -Uri "https://api.pinterest.com/v5/oauth/token" -Method Post -Headers $headers -Body $body
> ```

6. The response will contain:
   ```json
   {
     "access_token": "pina_XXXX...",
     "refresh_token": "pinr_XXXX...",
     "token_type": "bearer",
     "expires_in": 2592000
   }
   ```

7. Copy the values:
   - `access_token` → This is your `PINTEREST_ACCESS_TOKEN`
   - `refresh_token` → This is your `PINTEREST_REFRESH_TOKEN`

#### Step D: Get Your Board ID

You need to know which board to publish pins to.

1. Run this command (replace `YOUR_ACCESS_TOKEN`):

```bash
curl -X GET "https://api.pinterest.com/v5/boards" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

> **PowerShell:**
> ```powershell
> Invoke-RestMethod -Uri "https://api.pinterest.com/v5/boards" -Headers @{ "Authorization" = "Bearer YOUR_ACCESS_TOKEN" }
> ```

2. Find the board you want to post to and copy its `id` — this is your `PINTEREST_BOARD_ID`

> 💡 If you don't have a board yet, create one on Pinterest first (e.g., "Nail Art Inspiration"), then run the command above to get its ID.

---

## 🖥️ Step 2: Local Development (Optional)

### Install Dependencies

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/nailosmetic-pinterest-bot.git
cd nailosmetic-pinterest-bot

# Create a virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your actual API keys
notepad .env   # Windows
# nano .env    # Linux/macOS
```

### Run Locally

```bash
python main.py
```

---

## 🚀 Step 3: Deploy to GitHub

### 3.1 — Create a GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. Name it: `nailosmetic-pinterest-bot` (or anything you prefer)
3. Set it to **Private** (recommended, since it involves API keys)
4. **Do NOT** initialize with README (we already have one)
5. Click **Create Repository**

### 3.2 — Push Your Code

```bash
cd "g:\Nailosmetic Pinterest Automation App"

git init
git add .
git commit -m "🌸 Initial commit: Pinterest automation bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/nailosmetic-pinterest-bot.git
git push -u origin main
```

### 3.3 — Add GitHub Secrets

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"** and add each of these:

| Secret Name | Value |
|---|---|
| `GEMINI_API_KEY` | Your Google Gemini API key |
| `SILICONFLOW_API_KEY` | Your SiliconFlow API key |
| `PINTEREST_ACCESS_TOKEN` | Your Pinterest access token |
| `PINTEREST_BOARD_ID` | Your Pinterest board ID |
| `PINTEREST_REFRESH_TOKEN` | Your Pinterest refresh token |
| `PINTEREST_APP_ID` | Your Pinterest app ID |
| `PINTEREST_APP_SECRET` | Your Pinterest app secret |

### 3.4 — Test the Workflow

1. Go to the **Actions** tab in your repository
2. Click on **"📌 Daily Pinterest Pin"** workflow
3. Click **"Run workflow"** → **"Run workflow"**
4. Watch the logs to make sure everything works!

---

## ⏰ Schedule

The bot runs **automatically every day at 14:00 UTC** via GitHub Actions.

| Your Timezone | Equivalent Time |
|---|---|
| UTC | 2:00 PM |
| EST (UTC-5) | 9:00 AM |
| PST (UTC-8) | 6:00 AM |
| IST (UTC+5:30) | 7:30 PM |
| PKT (UTC+5) | 7:00 PM |

To change the schedule, edit the `cron` value in `.github/workflows/pinterest-bot.yml`:

```yaml
schedule:
  - cron: "0 14 * * *"  # Change this to your preferred time
```

> 💡 Use [crontab.guru](https://crontab.guru/) to build your cron expression.

---

## 🔄 Token Refresh

Pinterest access tokens expire after **30 days**. The bot automatically handles this:

1. Before publishing, it attempts to refresh the token using your `PINTEREST_REFRESH_TOKEN`
2. If successful, it uses the new token
3. **Important:** Pinterest issues a **new refresh token** each time. The bot will print it in the logs
4. You should update the `PINTEREST_REFRESH_TOKEN` secret in GitHub periodically

> ⚠️ If the token refresh fails and your access token has expired, you'll need to repeat **Step 1.3 (Steps C & D)** to get new tokens.

---

## 📁 Project Structure

```
nailosmetic-pinterest-bot/
├── .github/
│   └── workflows/
│       └── pinterest-bot.yml    # GitHub Actions daily cron job
├── .env.example                 # Template for environment variables
├── .gitignore                   # Protects .env from being committed
├── main.py                      # The main automation script
├── requirements.txt             # Python dependencies
└── README.md                    # This file!
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---|---|
| `Missing required environment variables` | Make sure all secrets are set in GitHub (Step 3.3) |
| `SiliconFlow API error 401` | Check your SiliconFlow API key is valid |
| `Pinterest API error 401` | Your access token has expired — refresh it (see Token Refresh section) |
| `Pinterest API error 403` | Your app may need approval, or you're missing required OAuth scopes |
| `Failed to parse Gemini response` | Gemini occasionally returns malformed JSON — the workflow will retry next day |
| `No TrueType font found` | Harmless warning on some systems, falls back to default font |

---

## 📄 License

This project is for personal use. Not affiliated with Pinterest, Google, or SiliconFlow.

---

**Built with 💅 for [Nailosmetic](https://nailosmetic.com)**

# 🔍 AI Media Authenticity Detector — Backend
### HackUNCP 2026 | FastAPI + Render

---

## 📁 What Each File Does

```
backend/
├── app.py                        ← The "front door" of your API. All requests come here first.
├── render.yaml                   ← Instructions for Render on how to deploy your app
├── requirements.txt              ← List of Python libraries to install
└── services/
    ├── __init__.py               ← Makes "services" a Python package (leave it empty)
    ├── metadata_analyzer.py      ← LAYER 3a: Checks EXIF/camera data
    ├── forensics_checker.py      ← LAYER 3b: Runs ELA and noise analysis
    ├── ai_classifier.py          ← LAYER 4:  Sends image to Hugging Face ML model
    └── scoring_engine.py         ← Combines all signals into a 0–100 risk score
```

---

## 🧠 How the Request Flow Works

```
User uploads image
       ↓
   app.py receives it
       ↓
   metadata_analyzer.py  → checks EXIF data
       ↓
   forensics_checker.py  → checks ELA + noise patterns
       ↓
   ai_classifier.py      → calls Hugging Face model
       ↓
   scoring_engine.py     → adds up all the signal weights → final score (0–100)
       ↓
   app.py returns JSON with risk_score, classification, and all signals
```

---

## 💻 Run It Locally First (Test Before Deploying)

### Step 1: Install Python
Make sure you have Python 3.10 or higher.
Check with: `python --version`

### Step 2: Install dependencies
Open a terminal, navigate into your `backend/` folder, and run:
```bash
pip install -r requirements.txt
```

### Step 3: Set your Hugging Face API token
Get a free token at https://huggingface.co → Settings → Access Tokens

**Mac/Linux:**
```bash
export HF_API_TOKEN=hf_your_token_here
```

**Windows (Command Prompt):**
```cmd
set HF_API_TOKEN=hf_your_token_here
```

**Windows (PowerShell):**
```powershell
$env:HF_API_TOKEN="hf_your_token_here"
```

### Step 4: Start the server
```bash
python app.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Step 5: Test it
Open http://localhost:8000 in your browser — you should see:
```json
{"status": "ok", "message": "AI Authenticity Detector is running!"}
```

To test the analysis endpoint, open http://localhost:8000/docs
This is the **automatic Swagger UI** — FastAPI generates it for free!
You can upload a test image right from your browser.

---

## 🚀 Deploy to Render (Step-by-Step for Beginners)

### What is Render?
Render is a cloud platform that hosts your Python backend.
It's like giving your code a permanent home on the internet so anyone can call your API.

---

### Step 1: Push Your Code to GitHub

You need your code on GitHub so Render can pull it.

1. Create a free account at https://github.com
2. Create a new repository (e.g., `ai-authenticity-detector`)
3. In your terminal, inside the `backend/` folder:

```bash
git init
git add .
git commit -m "Initial backend setup"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ai-authenticity-detector.git
git push -u origin main
```

---

### Step 2: Create a Render Account

1. Go to https://render.com
2. Click **"Get Started"** → Sign up (you can use your GitHub account!)

---

### Step 3: Create a New Web Service on Render

1. After logging in, click the **"New +"** button (top right)
2. Select **"Web Service"**
3. Click **"Connect account"** to link GitHub
4. Find your repo (`ai-authenticity-detector`) and click **"Connect"**

---

### Step 4: Configure the Service

Render will show you a settings page. Fill it in:

| Setting | Value |
|---|---|
| **Name** | `ai-authenticity-api` |
| **Region** | Oregon (US West) |
| **Branch** | `main` |
| **Root Directory** | *(leave blank if your code is at the root)* |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn app:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | `Free` |

> ⚠️ The `--port $PORT` is CRITICAL. Render picks the port dynamically.
> If you hardcode `--port 8000`, your app will crash on Render!

---

### Step 5: Add Your Secret Environment Variable

Still on the setup page, scroll down to **"Environment Variables"**.

Click **"Add Environment Variable"** and add:

| Key | Value |
|---|---|
| `HF_API_TOKEN` | `hf_your_hugging_face_token_here` |

> ✅ This keeps your secret token out of your code and GitHub repo.
> Never commit API tokens to GitHub!

---

### Step 6: Deploy!

Click **"Create Web Service"**.

Render will:
1. Pull your code from GitHub
2. Run `pip install -r requirements.txt` (you'll see the logs live)
3. Run `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. Give you a live URL like: `https://ai-authenticity-api.onrender.com`

The first deploy takes about 2–5 minutes. You can watch the logs in real time.

---

### Step 7: Test Your Live API

Visit `https://ai-authenticity-api.onrender.com`

You should see:
```json
{"status": "ok", "message": "AI Authenticity Detector is running!"}
```

Visit `https://ai-authenticity-api.onrender.com/docs` for the Swagger UI where you can test uploads.

---

## ⚡ Auto-Deploy on Code Changes

Every time you push to GitHub, Render automatically redeploys!

```bash
# Make a change in your code...
git add .
git commit -m "Fixed scoring engine"
git push
# Render detects the push and redeploys automatically ✅
```

---

## ❗ Common Problems & Fixes

### Problem: "Module not found" error
**Fix:** Make sure `requirements.txt` lists the missing module, then redeploy.

### Problem: "HF_API_TOKEN not set" in your results
**Fix:** Go to Render dashboard → your service → "Environment" tab → add the variable.

### Problem: App works locally but crashes on Render
**Fix:** Check that your start command uses `$PORT`, not a hardcoded port number.

### Problem: Render says "Build failed"
**Fix:** Click on the deploy in Render and read the logs — the error will be there.

### Problem: Hugging Face model returns 503
**Fix:** The model needs ~20 seconds to "warm up" on the free tier. Wait and retry.

---

## 🔗 Connect to Your Next.js Frontend

In your Next.js code, call the API like this:

```javascript
const formData = new FormData();
formData.append("file", selectedFile);

const response = await fetch("https://ai-authenticity-api.onrender.com/api/analyze", {
  method: "POST",
  body: formData,
});

const result = await response.json();
console.log(result.risk_score);     // 0-100
console.log(result.classification); // "low_risk", "medium_risk", "high_risk"
console.log(result.signals);        // detailed evidence breakdown
```

---

## 🗺️ What to Build Next (Post-Hackathon)

| Feature | File to Create |
|---|---|
| Reverse image search (Google/TinEye) | `services/source_verifier.py` |
| C2PA provenance verification | `services/provenance_checker.py` |
| Video frame extraction | `utils/video_processor.py` |
| Database to store results | Add SQLite or PostgreSQL |
| Rate limiting | Add slowapi middleware |

---

*Good luck at HackUNCP 2026! 🚀*

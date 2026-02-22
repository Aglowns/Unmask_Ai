# Deploy the whole app to Vercel

Frontend (Next.js) and backend (Python analyze API) both run on a single Vercel project.

## 1. Push your code to GitHub

Make sure your repo is on GitHub (or GitLab/Bitbucket).

## 2. Import the project on Vercel

1. Go to [vercel.com](https://vercel.com) and sign in (e.g. with GitHub).
2. Click **Add New…** → **Project**.
3. Import your **Unmask_AI-main** repository.
4. **Set Root Directory to `frontend`**
   - Click **Edit** next to “Root Directory”, choose `frontend`, then **Continue**.
5. Vercel will detect Next.js and will also deploy the Python API in `api/`.

## 3. Environment variables

In **Project Settings → Environment Variables** add:

| Name | Value | Required |
|------|--------|----------|
| `SIGHTENGINE_API_USER` | Your SightEngine API user | Recommended (better AI detection) |
| `SIGHTENGINE_API_SECRET` | Your SightEngine API secret | Recommended |
| `HF_API_TOKEN` | Your HuggingFace token (e.g. `hf_...`) | Optional fallback if SightEngine is not set |
| `NEXT_PUBLIC_API_URL` | Leave **empty** | So the app uses same-origin `/api/analyze` |

- **SightEngine:** Sign up at [sightengine.com](https://sightengine.com) (free tier: 2000 ops/month). Get `api_user` and `api_secret` from the dashboard.
- **HuggingFace:** Optional; used as fallback. Create a token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).

Leave `NEXT_PUBLIC_API_URL` unset so the frontend calls `/api/analyze` on the same Vercel deployment.

## 4. Deploy

Click **Deploy**. Vercel will:

- Build the Next.js app (pages, UI).
- Deploy the Python serverless function at `/api/analyze` (metadata, forensics, AI detection).

Your site will be at `https://your-project.vercel.app`. The “Get Started” → “Analyze” flow uses the same domain.

## Local development

- **Frontend only:** `npm run dev` in `frontend/`. Set `NEXT_PUBLIC_API_URL=http://localhost:8000` and run the repo-root FastAPI app (`python app.py`) so analyze works.
- **Full stack on Vercel:** Use `vercel dev` in `frontend/` to run Next.js and the Python API locally (requires Vercel CLI).

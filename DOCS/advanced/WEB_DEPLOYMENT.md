# Web Deployment Plan — GSM Clinical Inference 🌐

> How to publish the inference tool as a website so clinicians and
> researchers can upload patient data and receive predictions without
> installing Python locally.

---

## Architecture Overview

```
┌──────────────┐        HTTPS        ┌──────────────────────┐
│  Browser     │  ◄────────────────► │  Web Server           │
│  (upload CSV,│                      │  (Streamlit or Flask) │
│   view report│                      │                       │
│   download)  │                      │  ┌─────────────────┐  │
└──────────────┘                      │  │ Inference Engine │  │
                                      │  │ load_bundle()    │  │
                                      │  │ infer()          │  │
                                      │  │ multi_infer()    │  │
                                      │  └─────────────────┘  │
                                      │  ┌─────────────────┐  │
                                      │  │ .gsm.zip bundles │  │
                                      │  │ (pre-loaded)     │  │
                                      │  └─────────────────┘  │
                                      └──────────────────────┘
```

---

## Option 1: Streamlit Cloud (Recommended for Quick Start)

**What:** Free hosted Streamlit apps from a GitHub repository.

**Pros:**
- Zero server management — push code, it deploys
- Already have `src/ui/app.py` with inference tab built in
- Free tier: 1 GB RAM, public access
- HTTPS by default

**Cons:**
- 1 GB RAM limit can be tight for large bundles
- Apps sleep after inactivity (cold start ~30 seconds)
- Public only on free tier (no private apps)

**Monthly Cost:** **$0** (free tier)

**How to deploy:**
1. Ensure `dependencies.txt` lists all packages
2. Create `.streamlit/config.toml` with app settings
3. Connect your GitHub repo at [share.streamlit.io](https://share.streamlit.io)
4. Set entry point to `src/ui/app.py`
5. Deploy — URL will be `https://<your-app>.streamlit.app`

**Estimated setup time:** ~30 minutes

---

## Option 2: Hugging Face Spaces (Recommended for Research)

**What:** Free hosted ML demos using Streamlit or Gradio.

**Pros:**
- 16 GB RAM on free tier (generous for ML models)
- Research community visibility
- Docker support for full control
- Git LFS support for large bundles

**Cons:**
- Apps sleep after 48 hours of inactivity
- Cold start time can be slow with large dependencies

**Monthly Cost:** **$0** (free tier) or **$9/month** (persistent, no sleep)

**How to deploy:**
1. Create a Hugging Face Space (Streamlit SDK)
2. Push your code + pre-trained bundles in `models/pretrained/`
3. Add `requirements.txt` (same as `dependencies.txt`)
4. App auto-deploys in inference-only mode (training tabs hidden)

**HF-specific behaviour:**
The Streamlit app auto-detects the `SPACE_ID` environment variable
that HuggingFace injects.  When detected:
- Only the **Clinical Inference** and **Multi-Bundle Inference** tabs
  are shown (training and dataset explorer are hidden).
- Pre-trained bundles in `models/pretrained/` appear automatically
  in the bundle selector with a `[pretrained]` label.
- Users can also upload their own `.gsm.zip` files.

**Minimal HF Space structure:**
```
your-hf-space/
├── src/ui/app.py            # Streamlit entry point
├── src/inference/            # Inference engine
├── models/pretrained/        # Pre-trained .gsm.zip bundles
│   └── GDS1962_rf_seed44.gsm.zip
├── requirements.txt
└── README.md                 # HF Space card (with YAML header)
```

**Estimated setup time:** ~1 hour

---

## Option 3: Docker + Cloud VM

**What:** Full control via a Docker container on a cloud VM.

**Pros:**
- Complete control over resources
- No cold starts
- Can add authentication, database, persistent storage
- Works for production deployment

**Cons:**
- Requires Docker knowledge
- Must manage SSL certificates, security patches
- Pay-per-hour

### Provider Comparison

| Provider | vCPU | RAM | Monthly Cost | Free Tier |
|----------|------|-----|-------------|-----------|
| AWS EC2 (t3.small) | 2 | 2 GB | ~$15/month | 12 months free |
| Google Cloud (e2-small) | 2 | 2 GB | ~$13/month | $300 credit |
| Azure (B1ms) | 1 | 2 GB | ~$15/month | $200 credit |
| DigitalOcean (Basic) | 1 | 2 GB | $12/month | $200 credit |
| Hetzner (CX21) | 2 | 4 GB | **€4.50/month** | None |
| Railway | Auto | Auto | $5/month + usage | $5 credit |

**Recommended for budget:** Hetzner CX21 at €4.50/month

**Dockerfile (draft):**
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY dependencies.txt .
RUN pip install --no-cache-dir -r dependencies.txt

COPY src/ src/
COPY gsm/ gsm/
COPY data/patient_data/ data/patient_data/
COPY assets/ assets/

# Pre-trained bundles (ship with the image)
COPY models/pretrained/ models/pretrained/

EXPOSE 8501
CMD ["streamlit", "run", "src/ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

**Estimated setup time:** ~2–4 hours

---

## Option 4: Gradio + Hugging Face (Simplest UI)

**What:** Use Gradio instead of Streamlit for a simpler upload/predict UI.

**Pros:**
- Minimal code needed (~50 lines)
- Built-in API endpoint (REST)
- Easy sharing via Hugging Face

**Cons:**
- Less flexible than Streamlit
- Would need to write a new Gradio wrapper

**Monthly Cost:** **$0** on HF Spaces

---

## Security Considerations ⚠️

### Patient Data Privacy
- **HIPAA/GDPR:** If using real patient data, the server must comply
  with healthcare data regulations.
- **No server-side storage:** Process uploads in memory, never save
  patient CSVs to disk. Delete from memory after response.
- **HTTPS only:** All options above use HTTPS by default.
- **De-identification:** Recommend users strip patient identifiers
  before upload (use sample_001, sample_002, etc.).

### For Research Use
If this is for research demonstration (not clinical use):
- Free tiers are perfectly adequate
- Add a clear disclaimer on the web page
- No HIPAA compliance needed for de-identified data

---

## Recommendation

| Use Case | Best Option | Cost |
|----------|-------------|------|
| Quick demo / sharing | Streamlit Cloud | Free |
| Research community | Hugging Face Spaces | Free |
| Production with auth | Docker + Hetzner | ~€5/month |
| API endpoint | Gradio + HF Spaces | Free |

### For Your Case (Research Publication Tool)

**Start with Streamlit Cloud** — zero cost, zero maintenance, and you
already have the Streamlit app built.  If you need more RAM or want
to pre-load multiple bundles, upgrade to Hugging Face Spaces.

### Next Steps
1. Test the existing `src/ui/app.py` locally with `streamlit run src/ui/app.py`
2. Create a `.streamlit/config.toml` for theme/settings
3. Deploy to Streamlit Cloud or HF Spaces
4. Share the URL in your paper's supplementary materials

---

*Created: 2026-03-08*

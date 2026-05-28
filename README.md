# SupplyWatch

Geospatial supply-chain disruption monitoring. Monitors 68 major ports daily using free Sentinel-2 satellite imagery and Gemini Flash, and writes a structured briefing for each port.

**Live demo:** [supplywatch.tomoliveri.com](https://supplywatch.tomoliveri.com)

---

## What it does

Each day at 2am UTC a Cloud Run Job runs for each port in the watchlist:

1. Queries the [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/) STAC API for the latest Sentinel-2 L2A scene with cloud cover under 10%
2. Downloads the true-colour composite, crops it to a 2 km x 2 km area of interest and caches the JPEG in GCS
3. Runs a two-stage Gemini analysis: first a free-text observation of vessel counts, quay activity, yard fill and water conditions; then a structured assessment that weighs the imagery against weather data (Open-Meteo), labour events and geopolitical signals
4. Writes a `daily_briefings` document to Firestore with a severity score (1-5), confidence grade, disruption category and quantitative metrics

The Next.js frontend reads from Firestore in real time and displays the briefings on an interactive map.

---

## Architecture

```
Cloud Scheduler (2am UTC)
        |
        v
Cloud Run Job (Python 3.13)
    |       |       |       |
    v       v       v       v
CDSE     Vertex   Open-   Secret
STAC     AI       Meteo   Manager
API    (Gemini)   API     (creds)
    |       |
    v       v
   GCS   Firestore
(images) (briefings)
        |
        v
Cloud Run Service (Next.js 16)
        |
        v
Firebase Hosting (supplywatch.tomoliveri.com)
```

All GCP resources are managed by Terraform with remote state in GCS.

---

## Repository layout

```
backend/
  src/           Python pipeline modules
  scripts/       One-off admin scripts (ingest ports, cleanup, migrate)
  tests/         Integration test suite
  data/          Labour events and geopolitical events JSON
  Dockerfile     Cloud Run Job image
frontend/
  src/
    app/         Next.js App Router pages
    components/  React components
    hooks/       Firestore real-time subscription
    lib/         Firebase init, types, utilities
  Dockerfile     Cloud Run Service image (standalone Next.js)
terraform/       All GCP infrastructure as code
cloudbuild.yaml  Backend container build (invoked by Terraform)
firestore.rules  Firestore security rules
```

---

## Local development

### Prerequisites

- Python 3.13
- Node.js 20
- GCP project with Firestore, Vertex AI and GCS enabled
- [Copernicus Data Space account](https://dataspace.copernicus.eu/) (free)
- Firebase project (same GCP project)

### Frontend

```bash
cd frontend
cp .env.local.example .env.local
# Fill in .env.local with your Firebase config and Google Maps API key
npm install
npm run dev
```

The dashboard is at [http://localhost:3000/demo](http://localhost:3000/demo).

### Backend

```bash
pip install -r backend/requirements.txt

# Run the daily pipeline for all watchlist ports
GOOGLE_CLOUD_PROJECT=your-project \
GCS_BUCKET_NAME=your-imagery-bucket \
CDSE_USERNAME=your@email.com \
CDSE_PASSWORD=yourpassword \
python3 -m backend.src.main

# Run a 12-month historical backfill
BACKFILL_MONTHS=12 \
GOOGLE_CLOUD_PROJECT=your-project \
GCS_BUCKET_NAME=your-imagery-bucket \
CDSE_USERNAME=your@email.com \
CDSE_PASSWORD=yourpassword \
python3 -m backend.src.main
```

### Ingesting the port watchlist

```bash
GOOGLE_CLOUD_PROJECT=your-project python3 -m backend.scripts.ingest_ports
```

---

## Deployment

### Infrastructure

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Fill in billing_account_id and alert_email

terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

The backend Cloud Run Job is built and deployed by Terraform via a `null_resource` that calls `gcloud builds submit`. The `cloudbuild.yaml` at the root handles the backend container build.

### Frontend

Build and push the frontend container manually:

```bash
cd frontend
# Ensure .env.local exists with your Firebase and Maps API keys
gcloud builds submit . \
  --project=YOUR_PROJECT \
  --tag="REGION-docker.pkg.dev/YOUR_PROJECT/supply-chain-pipeline/frontend:latest"

gcloud run deploy supplywatch-dashboard \
  --image="REGION-docker.pkg.dev/YOUR_PROJECT/supply-chain-pipeline/frontend:latest" \
  --project=YOUR_PROJECT \
  --region=REGION
```

The `frontend/.gcloudignore` intentionally does not exclude `.env.*` files so that `.env.local` is included in the Cloud Build tarball and available to `next build`.

Then deploy Firebase Hosting to update the custom domain routing:

```bash
# From the repo root
npm install  # installs firebase-tools from package.json devDependencies
node_modules/.bin/firebase deploy --only hosting --project=YOUR_PROJECT
```

---

## Environment variables

### Frontend (`frontend/.env.local`)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_FIREBASE_API_KEY` | Firebase Web SDK API key |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | Firebase auth domain |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | GCP / Firebase project ID |
| `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET` | Firebase storage bucket |
| `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID` | Firebase messaging sender ID |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | Firebase app ID |
| `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` | Google Maps JavaScript API key |

Copy `frontend/.env.local.example` to `frontend/.env.local` to get started.

### Backend (runtime environment variables)

| Variable | Source | Description |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | Terraform / manual | GCP project ID |
| `GCS_BUCKET_NAME` | Terraform | Imagery cache bucket name |
| `CDSE_USERNAME` | Secret Manager `cdse-username` | CDSE OAuth username |
| `CDSE_PASSWORD` | Secret Manager `cdse-password` | CDSE OAuth password |
| `BACKFILL_MONTHS` | Manual (ad-hoc runs) | Set to N to run N months of historical backfill |

### Terraform (`terraform/terraform.tfvars`)

| Variable | Description |
|---|---|
| `billing_account_id` | GCP billing account ID |
| `alert_email` | Email for budget alert notifications |

Copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars` to get started.

---

## Cost

At current demo scale (68 ports, daily analysis):

| Service | Monthly (AUD) | Notes |
|---|---|---|
| Cloud Run Job | ~$3.00 | Scales to zero |
| Cloud Run Service | ~$2.00 | Scales to zero |
| Vertex AI (Gemini Flash) | ~$6.00 | 136 ports x 2 calls/day |
| Firestore | ~$1.50 | 1 write/port/day |
| GCS | ~$0.80 | ~136 JPEGs/month |
| Cloud Scheduler | ~$3.00 | 1 job/day |
| Secret Manager | ~$0.50 | 2 secrets |
| Sentinel-2 data | Free | EU Copernicus programme |
| Open-Meteo weather | Free | No API key required |
| **Total** | **~$17** | |

---

## Testing

```bash
# Run the integration test suite (requires live GCP credentials)
python3 -m pytest backend/tests/ -v
```

The integration tests (`test_golden_path.py`) run six stages end-to-end: geometry, STAC query, imagery, Gemini analysis, Firestore write, and round-trip read-back. The geometry test (`test_geometry.py`) validates bounding box and CRS correctness across equatorial, high-latitude and antimeridian-adjacent coordinate pairs.

---

## Firestore data model

### `watchlist_items`

Ports to monitor. Ingested via `backend/scripts/ingest_ports.py`.

| Field | Type | Description |
|---|---|---|
| `location_name` | string | Display name |
| `latitude` | float | WGS84 |
| `longitude` | float | WGS84 |
| `aoi_half_side_m` | float | Half-side of the square AOI in metres |

### `daily_briefings`

One document per port per analysis date.

| Field | Type | Description |
|---|---|---|
| `disruption_detected` | bool | Whether a disruption was flagged |
| `severity_score` | int | 1-5 |
| `confidence_grade` | string | High / Medium / Low |
| `explanation` | string | 2-4 sentence analyst summary |
| `disruption_category` | string | none / weather / labor / congestion / vessel_shift / yard_overflow / incident / other |
| `vessel_count` | int | At berth |
| `vessel_count_anchorage` | int | Offshore anchorage |
| `container_yard_fill_pct` | int | 0-100 |
| `weather_summary` | string | Open-Meteo summary |
| `geopolitical_active_events` | list[string] | Titles of active tracked events |
| `geopolitical_max_severity` | int | 1-5 |
| `current_image_path` | string | `gs://` URI |
| `baseline_image_path` | string | `gs://` URI |
| `analysed_at` | string | ISO 8601 UTC |
| `analysis_version` | int | 3 (current) |

---

## License

Apache 2.0

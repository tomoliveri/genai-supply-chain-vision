FROM python:3.13-slim

# libcurl4:   rasterio's bundled GDAL uses libcurl for /vsicurl/ HTTP-range
#             requests when reading remote JPEG-2000 tiles over HTTPS.
# libgomp1:   OpenMP thread pool used by rasterio and NumPy.
# libexpat1:  required by rasterio's bundled GDAL XML parser (missing in slim).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libcurl4 \
        libgomp1 \
        libexpat1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies before copying source so this layer is cached
# separately and only re-built when requirements.txt changes.
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy full backend package. PYTHONPATH=/app means 'backend' is a top-level
# package and all existing imports (from backend.src.*) resolve correctly.
COPY . backend/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Non-root execution for defence-in-depth; /tmp is world-writable so rasterio
# and Pillow scratch buffers are unaffected.
USER nobody

ENTRYPOINT ["python", "-m", "backend.src.main"]

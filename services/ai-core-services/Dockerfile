FROM python:3.11-slim

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    libgl1 \
    libglib2.0-0 \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and README
COPY pyproject.toml .
COPY README.md .

# Install dependencies using pip. Use CPU-only PyTorch index to prevent 4GB NVIDIA CUDA downloads.
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu .

COPY . .

EXPOSE 8002

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]

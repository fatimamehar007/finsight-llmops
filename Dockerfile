FROM python:3.11-slim

WORKDIR /app

# Install system deps for torch and chromadb
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create persistent storage directories
RUN mkdir -p chroma_db data

EXPOSE 8501 8000

# This image serves two distinct services from the same dependency set:
#   api service  -> uvicorn backend.api:app   (REST API: LLM, RAG, scoring, DB, PDF reports)
#   ui  service  -> streamlit run app/main.py (pure HTTP client of the api service)
# docker-compose.yml overrides `command` per service; this default runs the UI
# so `docker build . && docker run` still works standalone against a local API_BASE_URL.
CMD ["streamlit", "run", "app/main.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]

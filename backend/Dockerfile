FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/srv/.cache/huggingface

COPY backend/requirements.txt backend/requirements.txt
# CPU-only torch keeps the image small; the server never uses a GPU.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY eval eval

EXPOSE 8000
CMD ["sh", "-c", "cd backend && alembic upgrade head && cd .. && uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]

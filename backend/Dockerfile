FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend/ .
COPY sample_data/ /app/sample_data/
RUN useradd -m retailpilot && chown -R retailpilot:retailpilot /app
USER retailpilot
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

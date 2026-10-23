# Accounts.ai backend: FastAPI on Python 3.12, whatever Python the server itself has.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

WORKDIR /app
COPY requirements.txt constraints.txt ./
# constraints.txt pins the exact versions the app was tested with.
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

COPY app ./app

EXPOSE 8000
# One worker: the books are one SQLite file and the answer cache lives in memory.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

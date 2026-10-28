# Accounts.ai backend: FastAPI on Python 3.12, whatever Python the server itself has.
FROM python:3.12-slim

# Nothing is kept in the container: the books, uploads and chats are in the database (DATABASE_URL in backend/.env,
# passed in by docker compose), so the container can be rebuilt or replaced at any time.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt constraints.txt ./
# constraints.txt pins the exact versions the app was tested with (psycopg's binary wheels need no compiler or libpq).
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

COPY app ./app

EXPOSE 8000
# One worker: the answer caches, the chat prefetch and the background copies to Supabase and MongoDB live in this process.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

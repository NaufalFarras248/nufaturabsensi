FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY . .

# Railway menyuntikkan $PORT; server.py membaca --port.
EXPOSE 8080

CMD ["sh", "-c", "python server.py --host 0.0.0.0 --port ${PORT:-8080}"]

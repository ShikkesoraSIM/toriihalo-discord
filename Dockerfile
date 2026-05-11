FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY bot ./bot

RUN pip install --no-cache-dir .

RUN adduser --disabled-password --gecos "" botuser
USER botuser

CMD ["python", "-m", "bot.main"]


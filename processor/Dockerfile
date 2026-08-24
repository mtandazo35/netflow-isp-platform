FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends nfdump \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY processor.py .

CMD ["python", "processor.py"]

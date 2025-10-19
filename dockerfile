FROM python:3.10-slim

WORKDIR /app
COPY . .

RUN apt-get update && apt-get install -y wget curl unzip chromium chromium-driver && \
    pip install --no-cache-dir -r requirements.txt

ENV PATH="/usr/lib/chromium:${PATH}"
ENV CHROME_BIN="/usr/bin/chromium"

EXPOSE 5000
CMD ["python", "scraper.py"]

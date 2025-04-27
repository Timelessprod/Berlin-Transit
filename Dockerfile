FROM python:3.11-slim

RUN mkdir /berlin-transit
WORKDIR /berlin-transit

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /berlin-transit/entrypoint.sh

ENTRYPOINT ["/berlin-transit/entrypoint.sh"]

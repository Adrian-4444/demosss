FROM python:3.11-slim

WORKDIR /app

# Install system compiler tools for compiling bcrypt if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files
COPY . .

# Run DB seeding, then start application
CMD python app/seed_data.py && uvicorn app.main:app --host 0.0.0.0 --port 8000

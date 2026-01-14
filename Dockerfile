# Use a lightweight Python base image
FROM python:3.10-slim

# 1. Install system tools: Supervisor and Timezone Data
RUN apt-get update && apt-get install -y \
    supervisor \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 2. Set the Timezone to Nairobi (matches your requirement)
ENV TZ=Africa/Nairobi

WORKDIR /app

# 3. Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy your application code
COPY . .

# 5. Copy the supervisor configuration to the correct system folder
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 6. Expose the port Render expects
EXPOSE 10000

# 7. Start Supervisor (which will start Uvicorn, Celery, and Beat)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
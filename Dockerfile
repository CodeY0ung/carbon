FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY hub/ ./hub/

# Create .kube directory for kubeconfig
RUN mkdir -p /root/.kube

# Expose ports
EXPOSE 8000
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV KUBECONFIG=/root/.kube/config

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

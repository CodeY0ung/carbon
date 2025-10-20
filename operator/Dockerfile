FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy operator code
COPY operator.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the operator
CMD ["kopf", "run", "operator.py", "--verbose"]

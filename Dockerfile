
FROM python:3.11-slim
WORKDIR /app
COPY carbon_scheduler.py exporter.py requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "exporter.py"]

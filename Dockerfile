# Official Python 3.13 image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Expose the default HF Spaces port
EXPOSE 7860

CMD ["python", "app.py"]
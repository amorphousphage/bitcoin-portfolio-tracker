# Use official Python image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy requirements.txt first (to leverage Docker caching)
COPY requirements.txt /app/

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libssl-dev \
    libglib2.0-0 \
    libcairo2 \
    libpango-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 2222 for Flask
EXPOSE 2222

# Start the Flask application
CMD ["flask", "run", "--host=0.0.0.0", "--port=2222"]
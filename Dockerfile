# Use official OpenJDK 21 image
FROM openjdk:21-jdk-slim

# Set the working directory inside the container
WORKDIR /app

# Install Python, pip, and venv
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    fuse \
    gnupg \
    lsb-release \
    python3 \
    python3-pip \
    python3-venv && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \ 
    apt-get update && apt-get install -y nodejs && \
    echo "deb http://packages.cloud.google.com/apt gcsfuse-$(lsb_release -c -s) main" | tee /etc/apt/sources.list.d/gcsfuse.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - && \
    apt-get update && apt-get install -y gcsfuse && \
    rm -rf /var/lib/apt/lists/*

# Copy the application files to the container
COPY . .

# Create a virtual environment and install dependencies
RUN python3 -m venv /app/venv
RUN /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# Expose port 8000
EXPOSE 8000

# Set the working directory to src (since your main.py is inside src)
WORKDIR /app/src

# Run the FastAPI application using the virtual environment
CMD ["/app/venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

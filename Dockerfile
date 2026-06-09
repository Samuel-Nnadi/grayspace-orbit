FROM python:3.11-alpine

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy main script
COPY main.py .

# Run the script
ENTRYPOINT ["python", "/app/main.py"]

# 1. Use an official Python runtime as a parent image
FROM python:3.11-slim

# 2. Set the working directory in the container
WORKDIR /app

# 3. Copy the requirements file into the container
COPY requirements.txt .

# 4. Install dependencies
# We use --no-cache-dir to keep the image small
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your application code
COPY . .

# 6. Define the command to run your app using CMD which defines your runtime
# Cloud Run injects the PORT environment variable.
# We use shell form to ensure the variable expands correctly.
# Replace 'main:app' with 'your_filename:your_app_instance_name'
CMD exec uvicorn server_components.server:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips "*"
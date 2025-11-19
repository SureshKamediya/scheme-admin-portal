# Stage 1: Build Stage
FROM python:3.11-slim as builder

# Set environment variables for non-interactive python and to prevent writing pyc files
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Create and set working directory
WORKDIR /app

# Install system dependencies needed for python packages (like psycopg2-binary for Postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Production Stage
FROM python:3.11-slim

# Create a non-root user and set as primary user for security
RUN useradd -ms /bin/bash appuser
USER appuser
WORKDIR /app

# Copy installed packages from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/

# Copy the rest of the application code
COPY . /app/

# Expose the port Gunicorn will run on (e.g., 8000)
EXPOSE 8000

# Command to run the application using Gunicorn
# Replace `myproject.wsgi` with your actual project's WSGI file path (e.g., `your_project_name.wsgi:application`)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "myproject.wsgi:application"]
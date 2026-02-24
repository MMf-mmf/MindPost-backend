# Pull official base Python Docker image
FROM python:3.12.3-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
# ENV PYTHONPATH=/code
# ENV DJANGO_SETTINGS_MODULE=project.settings.staging
ENV PATH="/py/bin:$PATH"

# Install system dependencies including ffmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
    
# Set work directory
WORKDIR /code

# Create and activate virtual environment
RUN python -m venv /py && \
    /py/bin/pip install --upgrade pip

# Install dependencies
COPY project/requirements/ /code/requirements/
RUN /py/bin/pip install -r requirements/production.txt

# Create directory for static files and set permissions
RUN mkdir -p /code/staticfiles && \
    # Create non-root user for security
    adduser --disabled-password --no-create-home django-user && \
    chown -R django-user:django-user /code/staticfiles

# Copy project files
COPY . .

# Change ownership of application files
RUN chown -R django-user:django-user /code

# Switch to non-root user
USER django-user

# Collect static files, run migrations, and start Gunicorn
CMD python manage.py collectstatic --noinput && \
    python manage.py migrate --noinput && \
    exec gunicorn --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 8 \
    --timeout 0 \
    project.wsgi:application
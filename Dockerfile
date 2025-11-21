# Minimal Dockerfile using Python 3.13 slim
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.in .
# Install minimal build tools (only while installing dependencies), then remove them
RUN apt-get update \
	&& apt-get install -y --no-install-recommends build-essential gcc \
	&& pip install --upgrade pip setuptools wheel \
	&& pip install -r requirements.in \
	&& apt-get remove -y build-essential gcc \
	&& apt-get autoremove -y \
	&& rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Default command to run the bot. Adjust if you use a different entrypoint.
CMD ["python", "src/main.py"]

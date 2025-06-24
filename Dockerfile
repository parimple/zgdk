FROM python:3.10-slim-buster

# Install system dependencies (rarely change)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libxcb1 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Check the architecture
RUN uname -a

# Create app directory
WORKDIR /app

# Install Python dependencies (change less often than code)
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Download playwright browser (heavy operation, cache it)
RUN python -m playwright install chromium

# Check the executable permission of python binary
RUN ls -la $(which python)

# Copy only necessary files (exclude logs, cache, etc.)
COPY main.py ./
COPY cogs/ ./cogs/
COPY utils/ ./utils/
COPY datasources/ ./datasources/
COPY config.yml ./
COPY __init__.py ./

# Check the executable permission of main.py
RUN ls -la main.py

# Run the bot
CMD ["python", "main.py"]

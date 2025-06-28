FROM python:3.10-slim-buster

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
    dumb-init \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Check the architecture
RUN uname -a

# Create app directory
WORKDIR /app

# Install app dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Download the browser
RUN python -m playwright install chromium

# Check the executable permission of python binary
RUN ls -la $(which python)

# Copy the source code
COPY . .

# Check the executable permission of main.py
RUN ls -la main.py

# Use dumb-init to handle signals and prevent zombies
ENTRYPOINT ["dumb-init", "--"]

# Run the bot
CMD ["python", "main.py"]

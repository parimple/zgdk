FROM python:3.10-slim-buster

# Check the architecture
RUN uname -a

# Create app directory
WORKDIR /app

# Install app dependencies
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Check the executable permission of python binary
RUN ls -la $(which python)

# Copy the source code
COPY . .

# Check the executable permission of main.py
RUN ls -la main.py

# Run the bot
CMD ["python", "main.py", "&"]

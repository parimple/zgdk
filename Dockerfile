FROM python:3.11

# Create app directory
WORKDIR /app

# Install app dependencies
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy the source code
COPY . .

# Run the bot
CMD ["python", "main.py"]

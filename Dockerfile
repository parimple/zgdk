FROM python:3.10-slim-buster

# check the architecture
RUN uname -a

# Create app directory
WORKDIR /app

# Install app dependencies
COPY requirements.txt ./
RUN pip install -r requirements.txt

# check the executable permission of python binary
RUN ls -la $(which python)

# Copy the source code
COPY . .

# check the executable permission of main.py
RUN ls -la main.py

# Run the bot
CMD ["bash", "-c", "python main.py &"]

# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install development tools and debugger
RUN pip install --no-cache-dir debugpy

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Make port 80 available to the world outside this container
EXPOSE 80 5678

# Run discord_bot.py when the container launches with hot reload
CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "discord_bot.py"] 
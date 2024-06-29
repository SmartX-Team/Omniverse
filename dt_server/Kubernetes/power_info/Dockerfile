# Use the official Python base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 5001

# Set environment variables
ENV FLASK_APP=power_info.py
ENV FLASK_RUN_HOST=0.0.0.0

# Command to run the application
CMD ["flask", "run"]

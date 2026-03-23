# Use the official lightweight Python image
FROM python:3.11-slim

# Prevent Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE 1
# Prevent Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED 1

# Set the working directory inside the container
WORKDIR /code

# Install system dependencies required for PostgreSQL
# RUN apt-get install -y gcc libpq-dev \
#     && apt-get clean

# Copy the requirements file
COPY requirements.txt .

# Upgrade pip FIRST, then install dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual application code
COPY ./app /code/app

# Command to run the application using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
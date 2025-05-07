FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . /app

# Expose the port FastAPI is running on
EXPOSE 8000

# Run the FastAPI server using uvicorn
CMD ["uvicorn", "fast_api_server:app", "--host", "0.0.0.0", "--port", "8000"]
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY consistent_hash.py app.py ./

EXPOSE 5000

CMD ["python", "app.py"]

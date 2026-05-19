FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY data/ data/

RUN mkdir -p data

EXPOSE 5001

CMD ["python", "app.py"]

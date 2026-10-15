FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 5000

# FASE 1
CMD ["python", "app.py"]

# FASE 2: comenta la de arriba y descomenta esta
 CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
FROM python:3.13-slim

WORKDIR /app

# Dependencias de sistema mínimas (PyMuPDF y psycopg2-binary vienen con wheels,
# pero xhtml2pdf/reportlab necesitan libjpeg y zlib en runtime).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python primero para cachear la capa
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código de la app
COPY . .

# Directorio de uploads que la app puede escribir
RUN mkdir -p /app/static/uploads

EXPOSE 5002

CMD ["gunicorn", "app:app", \
     "--bind", "0.0.0.0:5002", \
     "--timeout", "120", \
     "--workers", "1", \
     "--worker-tmp-dir", "/dev/shm"]

# Gunakan base image dengan dukungan PostGIS
FROM python:3.11-slim

# Install dependensi sistem (termasuk GDAL)
RUN apt-get update && apt-get install -y \
    binutils \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set env vars untuk GDAL
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Set workdir
WORKDIR /app

# Salin requirements & install
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Salin seluruh kode ke container
COPY . .

# Buat direktori logs
RUN mkdir -p /app/logs

# Expose port
EXPOSE 8000

# Jalankan collectstatic tanpa interaktif
RUN python manage.py collectstatic --noinput

# Copy app.py
COPY app.py .

# Perintah default - jalankan Django dan notification service
CMD ["sh", "-c", "python app.py & gunicorn monitoringbackend.wsgi:application --bind 0.0.0.0:8000"]

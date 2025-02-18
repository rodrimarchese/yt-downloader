# Usa una imagen base ligera de Python
FROM python:3.9-slim

# Crea un directorio de trabajo en el contenedor
WORKDIR /app

# Copia los requisitos y los instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de tu proyecto
COPY . .

# Railway (y otras plataformas) suelen exponer la app por la variable PORT.
# Ajusta tu app para leer ese PORT o usa un valor por defecto (5000).
ENV PORT=5001

# Expone el puerto en Docker (opcional, algunos PaaS lo ignoran)
EXPOSE 5001

# Comando para arrancar la app.
# IMPORTANTE: En app.py, define app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
CMD ["python", "app.py"]

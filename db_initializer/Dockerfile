FROM python:3.12-slim

WORKDIR /engagement

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY db_initializer ./db_initializer

CMD ["python", "db_initializer/conexion_db.py"]
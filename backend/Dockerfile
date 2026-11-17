FROM python:3.12-slim

# Evita arquivos .pyc e faz o log aparecer na hora (sem buffer)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY . .
# Instalação "editável" (-e): o código em /app é usado diretamente,
# então o volume do docker-compose permite editar sem reconstruir a imagem.
RUN pip install -e ".[dev]"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Базовый образ Python с system dependencies (Debian-based, не Alpine!)
FROM python:3.11-slim

# Установка системных зависимостей для aiohttp и asyncpg
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Установка зависимостей
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Команда запуска (замени на свою entrypoint, если файл называется иначе)
CMD ["python", "bot.py"]
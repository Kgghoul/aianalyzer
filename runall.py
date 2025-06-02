import subprocess

# Запуск FastAPI
uvicorn_process = subprocess.Popen(
    ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
)

# Запуск Telegram-бота
bot_process = subprocess.Popen(
    ["python3", "backend/bot/bot.py"]
)

# Ожидание завершения
uvicorn_process.wait()
bot_process.wait()

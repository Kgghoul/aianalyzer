import schedule
import time
import subprocess
import sys
import logging
from pathlib import Path
from datetime import datetime

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / f"scheduler_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_collector():
    """Запуск скрипта сбора данных"""
    try:
        logger.info("Starting data collection job")
        result = subprocess.run(
            [sys.executable, "scripts/data_collector.py"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Data collection completed successfully")
        else:
            logger.error(f"Data collection failed with error: {result.stderr}")
            
    except Exception as e:
        logger.error(f"Error running data collector: {str(e)}")

def main():
    # Запускаем сбор данных каждый день в 00:00
    schedule.every().day.at("00:00").do(run_collector)
    
    # Также запускаем сразу при старте скрипта
    run_collector()
    
    logger.info("Scheduler started")
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Проверяем расписание каждую минуту
        except Exception as e:
            logger.error(f"Error in scheduler: {str(e)}")
            time.sleep(60)  # Продолжаем работу даже при ошибках

if __name__ == "__main__":
    main() 
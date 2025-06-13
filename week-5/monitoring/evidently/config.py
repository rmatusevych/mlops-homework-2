import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Конфігурація Evidently Cloud
    EVIDENTLY_API_KEY = os.getenv('EVIDENTLY_API_KEY', '')
    EVIDENTLY_URL = os.getenv('EVIDENTLY_URL', 'https://app.evidently.cloud')
    EVIDENTLY_PROJECT_ID = os.getenv('EVIDENTLY_PROJECT_ID', '019766db-c189-7f62-8bf4-442c2dcde7b0')
    EVIDENTLY_PROJECT_NAME = os.getenv('EVIDENTLY_PROJECT_NAME', 'YOLO Drift Monitoring')
    
    # Конфігурація ClickHouse
    CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'localhost')
    CLICKHOUSE_PORT = int(os.getenv('CLICKHOUSE_PORT', '30900'))
    CLICKHOUSE_USER = os.getenv('CLICKHOUSE_USER', 'default')
    CLICKHOUSE_PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', '')
    CLICKHOUSE_DATABASE = os.getenv('CLICKHOUSE_DATABASE', 'yolo_analytics')
    CLICKHOUSE_TABLE = os.getenv('CLICKHOUSE_TABLE', 'otel_traces')
    
    # Конфігурація еталонного набору даних
    REFERENCE_CLASS_NAME = os.getenv('REFERENCE_CLASS_NAME', 'car')
    REFERENCE_MIN_CONFIDENCE = float(os.getenv('REFERENCE_MIN_CONFIDENCE', '0.85'))
    REFERENCE_LIMIT = int(os.getenv('REFERENCE_LIMIT', '10'))
    
    # Конфігурація поточного набору даних
    CURRENT_DAYS_AGO = int(os.getenv('CURRENT_DAYS_AGO', '7'))
    
    # Конфігурація аналізу дрейфу
    REFERENCE_DATASET_ID = os.getenv('REFERENCE_DATASET_ID', '019766dc-3620-7831-9e0a-0b061e642f85')

    @classmethod
    def validate(cls) -> list:
        """Валідація обов'язкових налаштувань"""
        errors = []
        
        if not cls.EVIDENTLY_API_KEY:
            errors.append("EVIDENTLY_API_KEY is required")
        
        if not cls.REFERENCE_DATASET_ID:
            errors.append("REFERENCE_DATASET_ID is required (run create_reference_dataset.py first)")
            
        if cls.REFERENCE_MIN_CONFIDENCE < 0 or cls.REFERENCE_MIN_CONFIDENCE > 1:
            errors.append("REFERENCE_MIN_CONFIDENCE must be between 0 and 1")
            
        if cls.REFERENCE_LIMIT <= 0:
            errors.append("REFERENCE_LIMIT must be positive")
            
        if cls.CURRENT_DAYS_AGO <= 0:
            errors.append("CURRENT_DAYS_AGO must be positive")
        
        return errors
    
    @classmethod
    def print_config(cls):
        """Виводить поточну конфігурацію"""
        print(f"📊 Config: CH={cls.CLICKHOUSE_HOST}:{cls.CLICKHOUSE_PORT} | "
              f"Days={cls.CURRENT_DAYS_AGO} | "
              f"Ref={cls.REFERENCE_DATASET_ID[:8]}... | "
              f"Key={'✅' if cls.EVIDENTLY_API_KEY else '❌'}") 
              
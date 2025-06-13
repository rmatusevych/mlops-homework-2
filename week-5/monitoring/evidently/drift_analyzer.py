import logging
import sys
from datetime import datetime

from clickhouse_client import ClickHouseClient
from evidently_client import EvidentlyClient
from config import Config

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class YoloDriftAnalyzer:
    def __init__(self):
        self.clickhouse_client = ClickHouseClient()
        self.evidently_client = EvidentlyClient()
        logger.info("YOLO Drift Analyzer initialized")
    
    def analyze_drift(self) -> str:
        """
        Виконує аналіз дрифту:
        1. Завантажує reference датасет з Evidently Cloud
        2. Створює current датасет з ClickHouse (останні 7 днів)
        3. Створює та відправляє drift репорт у Cloud (з включеними current даними)
        """
        logger.info("Starting drift analysis...")
        
        try:
            # Перевіряємо конфігурацію
            if not Config.REFERENCE_DATASET_ID:
                raise Exception("REFERENCE_DATASET_ID is required. Create reference dataset first.")
            
            # Перевіряємо підключення до ClickHouse
            if not self.clickhouse_client.test_connection():
                raise Exception("ClickHouse connection failed")
            
            # Створюємо/отримуємо проект в Evidently
            project = self.evidently_client.create_or_get_project()
            
            # Отримуємо current дані з ClickHouse
            logger.info(f"Fetching current dataset (last {Config.CURRENT_DAYS_AGO} days)...")
            current_df = self.clickhouse_client.get_current_dataset()
            
            if current_df.empty:
                raise Exception(f"Current dataset is empty (no predictions in last {Config.CURRENT_DAYS_AGO} days)")
            
            logger.info(f"Current dataset: {len(current_df)} records")
            
            # Створюємо та завантажуємо drift репорт (current дані відправляються з репортом)
            logger.info("Creating drift report...")
            report_url = self.evidently_client.create_and_upload_drift_report(
                reference_dataset_id=Config.REFERENCE_DATASET_ID,
                current_df=current_df
            )
            
            logger.info("Drift analysis completed successfully")
            return report_url
            
        except Exception as e:
            logger.error(f"Error during drift analysis: {e}")
            raise

def main():
    """Головна функція"""
    print("🚀 YOLO Drift Analysis")
    print("=" * 30)
    
    # Валідація конфігурації
    errors = Config.validate()
    if errors:
        print("❌ Configuration errors:")
        for error in errors:
            print(f"   • {error}")
        sys.exit(1)
    
    try:
        analyzer = YoloDriftAnalyzer()
        report_url = analyzer.analyze_drift()
        
        print("✅ Analysis completed!")
        print(f"📊 Report: {report_url}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
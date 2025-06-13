import pandas as pd
from clickhouse_driver import Client
from typing import List, Dict, Any
import json
from datetime import datetime, timedelta
import logging

from config import Config

logger = logging.getLogger(__name__)

class ClickHouseClient:
    def __init__(self):
        self.client = Client(
            host=Config.CLICKHOUSE_HOST,
            port=Config.CLICKHOUSE_PORT,
            user=Config.CLICKHOUSE_USER,
            password=Config.CLICKHOUSE_PASSWORD,
            database=Config.CLICKHOUSE_DATABASE
        )
    
    def test_connection(self) -> bool:
        """Перевіряємо підключення до ClickHouse"""
        try:
            result = self.client.execute('SELECT 1')
            return True
        except Exception as e:
            logger.error(f"Помилка підключення до ClickHouse: {e}")
            return False
    
    def get_yolo_predictions_data(self, hours_ago: int = None, limit: int = None) -> pd.DataFrame:
        """
        Витягуємо дані YOLO передбачень з otel_traces
        
        Args:
            hours_ago: Отримати дані давніші за N годин тому
            limit: Обмежити кількість записів (для поточного набору даних)
        """
        # Повна назва таблиці з базою даних
        table_name = f"{Config.CLICKHOUSE_DATABASE}.{Config.CLICKHOUSE_TABLE}"
        
        query = f"""
        SELECT 
            Timestamp,
            SpanAttributes['prediction_id'] as prediction_id,
            SpanAttributes['processing_time_seconds'] as processing_time,
            SpanAttributes['filename'] as filename,
            SpanAttributes['model_name'] as model_name,
            arrayJoin(Events.Attributes)['class_name'] as class_name,
            arrayJoin(Events.Attributes)['confidence'] as confidence,
            arrayJoin(Events.Attributes)['object_index'] as object_index
        FROM {table_name}
        WHERE SpanName = 'yolo_prediction'
        """
        
        # Додаємо умову за часом, якщо вказано
        if hours_ago:
            query += f" AND Timestamp <= now() - INTERVAL {hours_ago} HOUR"
            query += f" AND Timestamp >= now() - INTERVAL {hours_ago + 24} HOUR"  # За добу від точки відліку
        
        # Сортування та ліміт
        query += " ORDER BY Timestamp DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        try:
            result = self.client.execute(query)
            
            # Створюємо DataFrame
            columns = [
                'timestamp', 'prediction_id', 'processing_time', 
                'filename', 'model_name', 'class_name', 'confidence', 'object_index'
            ]
            
            df = pd.DataFrame(result, columns=columns)
            
            # Перетворюємо типи даних
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['confidence'] = pd.to_numeric(df['confidence'], errors='coerce')
            df['processing_time'] = pd.to_numeric(df['processing_time'], errors='coerce')
            df['object_index'] = pd.to_numeric(df['object_index'], errors='coerce')
            
            return df
            
        except Exception as e:
            logger.error(f"Помилка запиту до ClickHouse: {e}")
            raise
    
    def get_reference_dataset(self) -> pd.DataFrame:
        """Отримуємо референсний набір даних (специфічні дані з високою впевненістю)"""
        # Повна назва таблиці з базою даних
        table_name = f"{Config.CLICKHOUSE_DATABASE}.{Config.CLICKHOUSE_TABLE}"
        
        query = f"""
        SELECT 
            Timestamp,
            SpanAttributes['prediction_id'] as prediction_id,
            SpanAttributes['processing_time_seconds'] as processing_time,
            SpanAttributes['filename'] as filename,
            SpanAttributes['model_name'] as model_name,
            arrayJoin(Events.Attributes)['class_name'] as class_name,
            arrayJoin(Events.Attributes)['confidence'] as confidence,
            arrayJoin(Events.Attributes)['object_index'] as object_index
        FROM {table_name}
        WHERE SpanName = 'yolo_prediction'
        ORDER BY Timestamp DESC
        """
        
        try:
            result = self.client.execute(query)
            
            # Создаем DataFrame
            columns = [
                'timestamp', 'prediction_id', 'processing_time', 
                'filename', 'model_name', 'class_name', 'confidence', 'object_index'
            ]
            
            df = pd.DataFrame(result, columns=columns)
            
            # Преобразуем типы данных
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['confidence'] = pd.to_numeric(df['confidence'], errors='coerce')
                df['processing_time'] = pd.to_numeric(df['processing_time'], errors='coerce')
                df['object_index'] = pd.to_numeric(df['object_index'], errors='coerce')
                
                filtered_df = df[
                    (df['class_name'] == Config.REFERENCE_CLASS_NAME) & 
                    (df['confidence'] > Config.REFERENCE_MIN_CONFIDENCE)
                ].head(Config.REFERENCE_LIMIT)
                
                return filtered_df
            else:
                return df
            
        except Exception as e:
            logger.error(f"Помилка запиту референсного набору даних: {e}")
            raise
    
    def get_current_dataset(self) -> pd.DataFrame:
        """Отримуємо поточний набір даних (прогнози за останні N днів)"""
        # Повна назва таблиці з базою даних
        table_name = f"{Config.CLICKHOUSE_DATABASE}.{Config.CLICKHOUSE_TABLE}"
        
        # Спрощений запит, як у референсному наборі даних
        query = f"""
        SELECT 
            Timestamp,
            SpanAttributes['prediction_id'] as prediction_id,
            SpanAttributes['processing_time_seconds'] as processing_time,
            SpanAttributes['filename'] as filename,
            SpanAttributes['model_name'] as model_name,
            arrayJoin(Events.Attributes)['class_name'] as class_name,
            arrayJoin(Events.Attributes)['confidence'] as confidence,
            arrayJoin(Events.Attributes)['object_index'] as object_index
        FROM {table_name}
        WHERE SpanName = 'yolo_prediction'
          AND Timestamp >= now() - INTERVAL {Config.CURRENT_DAYS_AGO} DAY
        ORDER BY Timestamp DESC
        """
        
        try:
            result = self.client.execute(query)
            
            # Создаем DataFrame
            columns = [
                'timestamp', 'prediction_id', 'processing_time', 
                'filename', 'model_name', 'class_name', 'confidence', 'object_index'
            ]
            
            df = pd.DataFrame(result, columns=columns)
            
            # Преобразуем типы данных
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['confidence'] = pd.to_numeric(df['confidence'], errors='coerce')
                df['processing_time'] = pd.to_numeric(df['processing_time'], errors='coerce')
                df['object_index'] = pd.to_numeric(df['object_index'], errors='coerce')
            
            return df
            
        except Exception as e:
            logger.error(f"Помилка запиту поточного набору даних: {e}")
            raise
    
    def get_predictions_summary(self) -> Dict[str, Any]:
        """Отримуємо зведену статистику передбачень"""
        table_name = f"{Config.CLICKHOUSE_DATABASE}.{Config.CLICKHOUSE_TABLE}"
        
        query = f"""
        SELECT 
            count() as total_predictions,
            countDistinct(SpanAttributes['prediction_id']) as unique_predictions,
            min(Timestamp) as earliest_prediction,
            max(Timestamp) as latest_prediction,
            avg(SpanAttributes['processing_time_seconds']) as avg_processing_time
        FROM {table_name}
        WHERE SpanName = 'yolo_prediction'
        """
        
        try:
            result = self.client.execute(query)
            if result:
                row = result[0]
                return {
                    'total_predictions': row[0],
                    'unique_predictions': row[1], 
                    'earliest_prediction': row[2],
                    'latest_prediction': row[3],
                    'avg_processing_time': float(row[4]) if row[4] else 0
                }
        except Exception as e:
            logger.error(f"Помилка отримання зведеної статистики передбачень: {e}")
            return {}
    
    def get_class_distribution(self, hours_ago: int = None) -> pd.DataFrame:
        """Отримуємо розподіл класів об'єктів"""
        table_name = f"{Config.CLICKHOUSE_DATABASE}.{Config.CLICKHOUSE_TABLE}"
        
        query = f"""
        SELECT 
            arrayJoin(Events.Attributes)['class_name'] as class_name,
            count() as count,
            avg(arrayJoin(Events.Attributes)['confidence']) as avg_confidence
        FROM {table_name}
        WHERE SpanName = 'yolo_prediction'
        """
        
        if hours_ago:
            query += f" AND Timestamp >= now() - INTERVAL {hours_ago} HOUR"
        
        query += " GROUP BY class_name ORDER BY count DESC"
        
        try:
            result = self.client.execute(query)
            df = pd.DataFrame(result, columns=['class_name', 'count', 'avg_confidence'])
            return df
        except Exception as e:
            logger.error(f"Помилка отримання розподілу класів: {e}")
            return pd.DataFrame() 
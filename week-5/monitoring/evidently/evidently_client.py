import pandas as pd
from evidently.ui.workspace import CloudWorkspace
from evidently import Dataset, DataDefinition, Report
from evidently.presets import DataDriftPreset
import logging
from typing import Dict, Any
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)

class EvidentlyClient:
    def __init__(self):
        if not Config.EVIDENTLY_API_KEY:
            raise ValueError("EVIDENTLY_API_KEY is required. Please set it in environment variables.")
        
        self.workspace = CloudWorkspace(
            token=Config.EVIDENTLY_API_KEY,
            url=Config.EVIDENTLY_URL
        )
        self.project = None
    
    def create_or_get_project(self) -> Any:
        """Створюємо або отримуємо існуючий проект"""
        try:
            # Якщо вказано конкретний PROJECT_ID, використовуємо його
            if Config.EVIDENTLY_PROJECT_ID:
                self.project = self.workspace.get_project(Config.EVIDENTLY_PROJECT_ID)
                return self.project
            
            # Пытаемся найти существующий проект по имени
            projects = self.workspace.list_projects()
            for project in projects:
                if project.name == Config.EVIDENTLY_PROJECT_NAME:
                    self.project = project
                    return project
            
            # Создаем новый проект если не найден
            self.project = self.workspace.create_project(Config.EVIDENTLY_PROJECT_NAME)
            return self.project
            
        except Exception as e:
            logger.error(f"Error creating/getting project: {e}")
            raise
    
    def prepare_dataset_for_evidently(self, df: pd.DataFrame, dataset_name: str) -> Dataset:
        """
        Готуємо DataFrame для роботи з Evidently
        
        Args:
            df: DataFrame з даними передбачень YOLO
            dataset_name: Ім'я набору даних
        """
        if df.empty:
            raise ValueError(f"DataFrame is empty for dataset: {dataset_name}")
        
        # Очищуємо дані
        df_clean = df.copy()
        df_clean = df_clean.dropna(subset=['class_name', 'confidence'])
        
        # Залишаємо лише основні ознаки для аналізу дрейфу YOLO
        features_df = df_clean[['class_name', 'confidence', 'processing_time']]
        
        # Створюємо Dataset для Evidently
        dataset = Dataset.from_pandas(pd.DataFrame(features_df))
        
        return dataset
    
    def upload_dataset(self, df: pd.DataFrame, dataset_name: str, description: str = "") -> str:
        """Завантажуємо набір даних у Evidently Cloud"""
        if not self.project:
            raise ValueError("Project not initialized. Call create_or_get_project() first")
        
        try:
            # Готуємо набір даних
            dataset = self.prepare_dataset_for_evidently(df, dataset_name)
            
            # Завантажуємо в Cloud (використовуємо правильний API)
            dataset_id = self.workspace.add_dataset(
                dataset=dataset,
                name=dataset_name,
                project_id=self.project.id,
                description=description or f"YOLO predictions dataset uploaded at {datetime.now()}"
            )
            
            return dataset_id
            
        except Exception as e:
            logger.error(f"Error uploading dataset '{dataset_name}': {e}")
            raise
    
    def download_dataset(self, dataset_id: str) -> pd.DataFrame:
        """Завантажуємо набір даних з Evidently Cloud"""
        try:
            # Завантажуємо набір даних
            dataset = self.workspace.load_dataset(dataset_id=dataset_id)
            
            # Преобразуем в DataFrame
            df = dataset.as_dataframe()
            
            return df
            
        except Exception as e:
            logger.error(f"Error downloading dataset {dataset_id}: {e}")
            raise
    
    def create_and_upload_drift_report(self, reference_dataset_id: str, current_df: pd.DataFrame) -> str:
        """
        Створюємо звіт про дрейф, використовуючи reference з Cloud та поточні дані
        
        Args:
            reference_dataset_id: ID reference набору даних у Evidently Cloud
            current_df: Поточні дані (відправляються зі звітом)
            
        Returns:
            URL звіту в Evidently Cloud
        """
        try:
            # Створюємо/отримуємо проект
            self.create_or_get_project()
            
            # Завантажуємо reference набір даних з Cloud
            reference_df = self.download_dataset(reference_dataset_id)
            
            # Готуємо набори даних
            reference_dataset = self.prepare_dataset_for_evidently(reference_df, "reference")
            current_dataset = self.prepare_dataset_for_evidently(current_df, "current")
            
            # Створюємо звіт про дрейф з метаданими
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report = Report(
                metrics=[DataDriftPreset()],
                tags=[
                    "yolo_monitoring",
                    f"reference_dataset:{reference_dataset_id}",
                    f"created:{timestamp}"
                ]
            )
            
            # Запускаємо аналіз - отримуємо snapshot
            my_eval = report.run(current_data=current_dataset, reference_data=reference_dataset)
            
            # Завантажуємо snapshot в Evidently Cloud, використовуючи правильний API
            run_id = self.workspace.add_run(
                self.project.id, 
                my_eval,
                include_data=True
            )
            
            # Формуємо URL для перегляду звіту
            report_url = f"{Config.EVIDENTLY_URL}/projects/{self.project.id}/reports/{run_id}"
            
            return report_url
            
        except Exception as e:
            logger.error(f"Error creating drift report: {e}")
            raise 
import torch
from fastapi.responses import JSONResponse
from fastapi import FastAPI
from ultralytics import YOLO
import subprocess
import sys
import os
import wandb

import ray
from ray import serve
from ray.serve.handle import DeploymentHandle

#serve.start(http_options={"host": "0.0.0.0", "port": 8001})

app = FastAPI()

@serve.deployment(
    num_replicas=1,
    ray_actor_options={
        "num_cpus": 1,
    }
)
@serve.ingress(app)
class APIIngress:
    def __init__(self, object_detection_handle) -> None:
        self.handle: DeploymentHandle = object_detection_handle.options(
            use_new_handle_api=True,
        )

    @app.get("/detect")
    async def detect(self, image_url: str):
        result = await self.handle.detect.remote(image_url)
        return JSONResponse(content=result)


@serve.deployment(
    autoscaling_config={"min_replicas": 1, "max_replicas": 2},
    ray_actor_options={
        "num_cpus": 1,
    }
)
class ObjectDetection:
    def __init__(self):
        # Конфігурація wandb
        self.wandb_project = os.getenv("WANDB_PROJECT", "model-registry")
        self.wandb_entity = os.getenv("WANDB_ENTITY", "dmytro-spodarets") 
        self.model_artifact_name = os.getenv("WANDB_MODEL_ARTIFACT", "dmytro-spodarets/model-registry/YOLO-NEW:v1")
        
        print("🤖 Ініціалізація wandb та завантаження моделі YOLO...")
        
        # Переконуємося, що wandb в online режимі для завантаження артефактів
        os.environ["WANDB_MODE"] = "online"
        
        # Ініціалізація wandb
        run = wandb.init(
            project=self.wandb_project,
            entity=self.wandb_entity,
            job_type="inference",
            mode="online"  # Явно вказуємо online режим
        )
        
        try:
            # Перевіряємо наявність API ключа
            api_key = os.getenv("WANDB_API_KEY")
            if not api_key:
                raise ValueError("WANDB_API_KEY not found in environment variables")
            
            # Завантаження артефакту моделі з wandb
            print(f"📥 Завантаження артефакту моделі: {self.model_artifact_name}")
            artifact = run.use_artifact(self.model_artifact_name, type='model')
            model_path = artifact.download()
            
            # Пошук файлу моделі в завантаженій директорії
            model_file = None
            for file in os.listdir(model_path):
                if file.endswith('.pt'):
                    model_file = os.path.join(model_path, file)
                    break
            
            if model_file is None:
                raise FileNotFoundError("No .pt model file found in the downloaded artifact")
            
            print(f"📁 Шлях до файлу моделі: {model_file}")
            self.model = YOLO(model_file)
            print("✅ Модель успішно завантажена з wandb!")
            
        except Exception as e:
            print(f"❌ Не вдалося завантажити модель з wandb: {e}")
            print("🔄 Перехід до резервної моделі yolov8n.pt...")
            self.model = YOLO('yolov8n.pt')
            print("✅ Резервна модель успішно завантажена!")
        
        finally:
            # Завершуємо wandb run після завантаження моделі
            wandb.finish()

    async def detect(self, image_url: str):
        results = self.model(image_url)

        detected_objects = []
        if len(results) > 0:
            for result in results:
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    object_name = result.names[class_id]
                    coords = box.xyxy[0].tolist()
                    detected_objects.append({"class": object_name, "coordinates": coords})

        if len(detected_objects) > 0:
            return {"status": "found", "objects": detected_objects}
        else:
            return {"status": "not found"}

entrypoint = APIIngress.bind(ObjectDetection.bind())

import torch
from fastapi.responses import JSONResponse
from fastapi import FastAPI
from ultralytics import YOLO
import subprocess
import sys
import os
import wandb
import base64
import cv2
import numpy as np
from pydantic import BaseModel
from typing import Optional
import tempfile

import ray
from ray import serve
from ray.serve.handle import DeploymentHandle

#serve.start(http_options={"host": "0.0.0.0", "port": 8001})

app = FastAPI()

class ImageRequest(BaseModel):
    image_data: str  # base64 encoded image
    image_url: Optional[str] = None  # optional for backward compatibility

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
    async def detect_get(self, image_url: str):
        # Keep GET endpoint for backward compatibility
        result = await self.handle.detect_url.remote(image_url)
        return JSONResponse(content=result)

    @app.post("/detect")
    async def detect_post(self, request: ImageRequest):
        if request.image_data:
            # Handle base64 encoded image
            result = await self.handle.detect_base64.remote(request.image_data)
        elif request.image_url:
            # Handle image URL for backward compatibility
            result = await self.handle.detect_url.remote(request.image_url)
        else:
            return JSONResponse(content={"error": "Either image_data or image_url must be provided"}, status_code=400)
        
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

    async def detect_url(self, image_url: str):
        # Original method for URL-based detection
        results = self.model(image_url)
        return self._process_results(results)

    async def detect_base64(self, image_data: str):
        # New method for base64-encoded image detection
        try:
            # Decode base64 image
            image_bytes = base64.b64decode(image_data)
            
            # Convert to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            
            # Decode image
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                return {"error": "Failed to decode image"}
            
            # Create temporary file for YOLO inference
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                cv2.imwrite(tmp_file.name, image)
                tmp_path = tmp_file.name
            
            try:
                # Run inference
                results = self.model(tmp_path)
                return self._process_results(results)
            finally:
                # Clean up temporary file
                os.unlink(tmp_path)
                
        except Exception as e:
            return {"error": f"Failed to process image: {str(e)}"}

    def _process_results(self, results):
        # Common method to process YOLO results
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

    # Keep original method for backward compatibility
    async def detect(self, image_url: str):
        return await self.detect_url(image_url)

entrypoint = APIIngress.bind(ObjectDetection.bind())

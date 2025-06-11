# Video Link for the Homework 2:
https://www.loom.com/share/fc203cdba0ab4dd3aeb7ce3dea9c6f08?sid=e248d2b0-82cb-436f-95c2-c2ec9b3ef54d

# Video Link for the Homework 3:
https://www.loom.com/share/aae4ab34cb0241f592ac971b638adda1?sid=81c822dd-68a7-495a-a444-24a4adc220f5

# MLOps Homework 2: Distributed YOLO Training with Ray

This project demonstrates a complete MLOps pipeline for training YOLOv8 object detection models using Ray for distributed computing, Kubernetes for orchestration, and Weights & Biases for experiment tracking.

## 🎯 Project Overview

This homework implements a distributed machine learning training system for mushroom detection using YOLOv8. The system leverages modern MLOps tools and practices to create a scalable, reproducible training pipeline.

### Key Features

- **YOLOv8 Object Detection**: Custom mushroom detection model training
- **Distributed Computing**: Ray cluster for scalable training
- **Container Orchestration**: Kubernetes deployment with monitoring
- **Experiment Tracking**: Weights & Biases integration for MLOps observability
- **CPU Optimized**: Designed for CPU-based training environments

## 🏗️ Project Structure

```
├── yolo-cpu/                 # Core training components
│   ├── train_yolo.py        # Main YOLO training script
│   ├── ray_job.py           # Ray job wrapper
│   ├── submit_job.py        # Job submission utilities
│   ├── config.yaml          # Training configuration
│   ├── mushroom_dataset.yaml # Dataset configuration
│   └── requirements.txt     # Python dependencies
├── dataset/                  # Training dataset
│   ├── images/              # Training images
│   ├── labels/              # YOLO format annotations
│   └── classes.txt          # Object classes (Mushroom)
├── k8s/                     # Kubernetes infrastructure
│   ├── ray-cluster/         # Ray cluster manifests
│   ├── monitoring/          # Monitoring setup
│   ├── docker/              # Docker configurations
│   └── setup_cluster.sh     # Cluster setup script
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker
- Kubernetes cluster (or Kind for local development)
- Weights & Biases account

### 1. Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd mlops-homework-2

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
cd yolo-cpu
pip install -r requirements.txt
```

### 2. Configure Weights & Biases

```bash
# Set your W&B API key
export WANDB_API_KEY="your-wandb-api-key"

# Or create a .env file
echo "WANDB_API_KEY=your-wandb-api-key" > .env
```

### 3. Local Training

```bash
# Run local training
python train_yolo.py
```

### 4. Kubernetes Deployment

```bash
# Setup Ray cluster on Kubernetes
cd ../k8s
chmod +x setup_cluster.sh
./setup_cluster.sh

# Submit distributed training job
cd ../yolo-cpu
python submit_job.py
```

## 📊 Dataset

The project uses a custom mushroom detection dataset:

- **Classes**: 1 (Mushroom)
- **Format**: YOLO format annotations
- **Structure**: Images in `dataset/images/`, labels in `dataset/labels/`

## ⚙️ Configuration

Training parameters can be modified in `yolo-cpu/config.yaml`:

```yaml
model: yolov8n.pt          # YOLO model variant
epochs: 3                  # Training epochs
batch: 16                  # Batch size
imgsz: 640                 # Image size
device: cpu                # Training device
optimizer: "Adam"          # Optimizer
lr0: 0.01                 # Learning rate
wandb_project: "setuniversity-mlops"  # W&B project name
```

## 🔧 Ray Integration

The project uses Ray for distributed training:

- **Ray Job**: `ray_job.py` handles distributed execution
- **Job Submission**: `submit_job.py` manages Ray job lifecycle
- **Auto-scaling**: Kubernetes-based Ray cluster with auto-scaling capabilities

## 📈 Monitoring & Observability

- **Weights & Biases**: Automatic experiment tracking and metrics logging
- **Kubernetes Monitoring**: Built-in monitoring stack in `k8s/monitoring/`
- **Ray Dashboard**: Ray cluster monitoring and job management

## 🐳 Docker Support

Docker configurations are available in `k8s/docker/` for:
- Training job containers
- Ray cluster components
- Custom environment setups

## 📝 MLOps Best Practices

This project demonstrates:

1. **Reproducible Experiments**: Configuration-driven training with version control
2. **Scalable Infrastructure**: Kubernetes-based deployment with auto-scaling
3. **Experiment Tracking**: Comprehensive logging with W&B
4. **Infrastructure as Code**: Kubernetes manifests and setup scripts
5. **Containerization**: Docker-based deployment strategy

## 🤝 Contributing

This is a homework project for SET University MLOps course.

## 📚 Resources

- [YOLOv8 Documentation](https://docs.ultralytics.com/)
- [Ray Documentation](https://docs.ray.io/)
- [Weights & Biases](https://wandb.ai/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)

## 📄 License

This project is created for educational purposes as part of SET University MLOps course.

# Моніторинг та Observability у MLOps

## Підключення моніторингу до Ray кластеру

week-3/k8s/ray-cluster/ray-cluster-values.yaml

```bash
./setup_cluster.sh
```

## Моніторинг метрик роботи моделі

Розгортання моделі, OpenTelemetry Collector, ClickHouse, Grafana, Prometheus, Node Exporter

```bash
cd week-5
docker compose up --build -d
```

Сервіси будуть доступні:
YOLO API:           http://localhost:30080
ClickHouse:         http://localhost:30123 (Web UI: http://localhost:30123/play)
Prometheus:         http://localhost:30091
Grafana:            http://localhost:30001 (admin/admin)
OpenTelemetry:      http://localhost:30888/metrics
Node Exporter:      http://localhost:30100/metrics

Використання моделі
```bash
curl -X POST http://localhost:30080/detect -F "file=@cars/8.jpg"
#чи
python yolo/client.py cars/1.jpg
#чи 
python yolo/client.py https://example.com/image.jpg
```

Перевіряємо ClickHouse та Grafana

## Детекція data drift

Створити акаунт в https://www.evidentlyai.com/

Чи розгорнути локально - https://docs.evidentlyai.com/docs/setup/self-hosting 

Налаштування оточення .env

Створення Reference Dataset

```bash
python create_reference_dataset.py
```

Запуск аналізу дрифту

```bash
python drift_analyzer.py
```
Результат: 
https://app.evidently.cloud/projects/your_project/reports/your_report

Побудова дашборда у Evidently

#!/bin/bash

set -e 

echo "=== 0. Cleaning up any existing cluster ==="
# Kill any existing port forwards
pkill -f "kubectl port-forward.*raycluster-kuberay-head-svc" || true
pkill -f "kubectl port-forward.*prometheus" || true
pkill -f "kubectl port-forward.*grafana" || true

# Delete existing cluster if it exists
kind delete cluster --name ray-cluster || true

# Clean up docker resources that might be hanging
docker system prune -f --volumes || true

echo "=== 1. Starting Kind cluster ==="
mkdir -p /tmp/kubeflow-data

# Add retry logic for cluster creation
for i in {1..3}; do
    echo "Attempt $i/3: Creating Kind cluster..."
    if kind create cluster --config kind/kind-config.yaml; then
        echo "✅ Kind cluster created successfully"
        break
    else
        echo "❌ Kind cluster creation failed on attempt $i"
        if [ $i -eq 3 ]; then
            echo "❌ Failed to create Kind cluster after 3 attempts"
            exit 1
        fi
        echo "⏳ Waiting 30 seconds before retry..."
        kind delete cluster --name ray-cluster || true
        sleep 30
    fi
done

# Wait for cluster to be ready with extended timeout
echo "Waiting for cluster to be ready..."
kubectl wait --for=condition=ready nodes --all --timeout=600s

# Verify cluster is healthy
echo "Verifying cluster health..."
kubectl get nodes -o wide
kubectl cluster-info

echo "=== 2. Installing Prometheus Stack ==="
# Add Helm repositories with retry
for i in {1..3}; do
    if helm repo add prometheus-community https://prometheus-community.github.io/helm-charts && \
       helm repo add kuberay https://ray-project.github.io/kuberay-helm/ && \
       helm repo update; then
        echo "✅ Helm repositories added successfully"
        break
    else
        echo "❌ Failed to add Helm repositories on attempt $i"
        if [ $i -eq 3 ]; then
            echo "❌ Failed to add Helm repositories after 3 attempts"
            exit 1
        fi
        sleep 10
    fi
done

# Create namespace for prometheus
kubectl create namespace prometheus-system || true

# Install kube-prometheus-stack with retry
echo "Installing kube-prometheus-stack..."
for i in {1..3}; do
    if helm install prometheus prometheus-community/kube-prometheus-stack \
        --namespace prometheus-system \
        --version 61.7.2 \
        -f monitoring/prometheus/prometheus-values.yaml \
        --timeout 10m; then
        echo "✅ Prometheus stack installed successfully"
        break
    else
        echo "❌ Prometheus installation failed on attempt $i"
        if [ $i -eq 3 ]; then
            echo "❌ Failed to install Prometheus after 3 attempts"
            exit 1
        fi
        echo "⏳ Cleaning up and retrying..."
        helm uninstall prometheus -n prometheus-system || true
        sleep 30
    fi
done

echo "=== 3. Waiting for Prometheus stack to be ready ==="
echo "Waiting for Prometheus operator..."
kubectl wait --for=condition=available --timeout=600s deployment/prometheus-kube-prometheus-operator -n prometheus-system

echo "Waiting for Prometheus StatefulSet to be created..."
for i in {1..30}; do
    if kubectl get statefulset prometheus-prometheus-kube-prometheus-prometheus -n prometheus-system >/dev/null 2>&1; then
        echo "✅ Prometheus StatefulSet found"
        break
    fi
    echo "⏳ Prometheus StatefulSet not found yet, waiting... (attempt $i/30)"
    sleep 10
done

echo "Waiting for Prometheus pod to be ready..."
kubectl wait --for=condition=ready --timeout=600s pod/prometheus-prometheus-kube-prometheus-prometheus-0 -n prometheus-system

echo "Waiting for Grafana..."
kubectl wait --for=condition=ready --timeout=600s pod -l app.kubernetes.io/name=grafana -n prometheus-system

echo "=== 4. Installing KubeRay operator ==="
for i in {1..3}; do
    if helm install kuberay-operator kuberay/kuberay-operator --version 1.3.2 --timeout 5m; then
        echo "✅ KubeRay operator installed successfully"
        break
    else
        echo "❌ KubeRay operator installation failed on attempt $i"
        if [ $i -eq 3 ]; then
            echo "❌ Failed to install KubeRay operator after 3 attempts"
            exit 1
        fi
        helm uninstall kuberay-operator || true
        sleep 30
    fi
done

echo "=== 5. Waiting for KubeRay operator to be ready ==="
kubectl wait --for=condition=available --timeout=600s deployment/kuberay-operator

echo "Checking operator status..."
kubectl get deployment kuberay-operator -o wide

echo "=== 5.1. Checking and fixing node scheduling ==="
echo "Current node status:"
kubectl get nodes -o wide
kubectl describe nodes | grep -A 3 -B 3 "Taints\|Allocatable"

echo "Removing control-plane taints to allow scheduling..."
kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true
kubectl taint nodes --all node-role.kubernetes.io/master- || true

echo "Updated node status:"
kubectl get nodes -o wide

echo "=== 6. Installing Ray cluster with SCALE-TO-ZERO autoscaling ==="
for i in {1..3}; do
    if helm install raycluster kuberay/ray-cluster --version 1.3.2 -f ray-cluster/ray-cluster-values.yaml --timeout 10m; then
        echo "✅ Ray cluster installed successfully"
        break
    else
        echo "❌ Ray cluster installation failed on attempt $i"
        if [ $i -eq 3 ]; then
            echo "❌ Failed to install Ray cluster after 3 attempts"
            exit 1
        fi
        helm uninstall raycluster || true
        sleep 30
    fi
done

echo "=== 7. Installing monitoring configuration ==="
for i in {1..3}; do
    if kubectl apply -f monitoring/prometheus/ray-servicemonitor.yaml && \
       kubectl apply -f monitoring/prometheus/ray-podmonitor.yaml && \
       kubectl apply -f monitoring/prometheus/ray-prometheus-rules.yaml; then
        echo "✅ Monitoring configuration applied successfully"
        break
    else
        echo "❌ Monitoring configuration failed on attempt $i"
        if [ $i -eq 3 ]; then
            echo "❌ Failed to apply monitoring configuration after 3 attempts"
            exit 1
        fi
        sleep 10
    fi
done

echo "=== 8. Waiting for Ray cluster to be ready ==="

wait_for_resource_to_exist() {
    local resource_type=$1
    local selector=$2
    local description=$3
    
    echo "Waiting for $description to be created..."
    for i in {1..60}; do
        if kubectl get $resource_type -l $selector --no-headers 2>/dev/null | grep -q .; then
            echo "✅ $description found"
            return 0
        fi
        echo "⏳ $description not found yet, waiting... (attempt $i/60)"
        sleep 10
    done
    echo "❌ Timeout waiting for $description"
    return 1
}

wait_for_resource_to_exist "pod" "ray.io/node-type=head" "head pod"

echo "Checking head pod status and events..."
kubectl get pods -l ray.io/node-type=head -o wide
kubectl describe pod -l ray.io/node-type=head

echo "Waiting for head pod to be ready..."
# Increase timeout from 900s to 1800s (30 minutes)
kubectl wait --for=condition=ready --timeout=900s pod -l ray.io/node-type=head

echo "=== 9. Verifying cluster health ==="
# Перевіряємо статус кластера
echo "Checking cluster status..."
kubectl get pods -l ray.io/cluster-name -o wide

# Перевіряємо статус Ray всередині кластера
echo "Checking Ray status..."
HEAD_POD=$(kubectl get pod -l ray.io/node-type=head -o jsonpath='{.items[0].metadata.name}')
if [ ! -z "$HEAD_POD" ]; then
    echo "Head pod found: $HEAD_POD"
    
    echo "Waiting for Ray to be ready inside head pod..."
    for i in {1..10}; do
        if kubectl exec $HEAD_POD -- ray status 2>/dev/null; then
            echo "✅ Ray is ready!"
            break
        fi
        echo "⏳ Ray not ready yet, attempt $i/10..."
        sleep 15
    done
    
    # Тепер, коли Ray готовий, спробуємо отримати dashboard
    echo "Extracting Ray dashboards from ready Ray cluster..."
    RAY_SESSION=$(kubectl exec $HEAD_POD -c ray-head -- find /tmp/ray -name "session_*" -type d 2>/dev/null | head -1)
    if [ ! -z "$RAY_SESSION" ]; then
        echo "✅ Found Ray session: $RAY_SESSION"
        
        # Спочатку налаштовуємо port-forward для Grafana
        echo "Setting up Grafana port-forward..."
        pkill -f "kubectl port-forward.*grafana" || true
        kubectl port-forward svc/prometheus-grafana -n prometheus-system 3000:80 > /dev/null 2>&1 &
        sleep 5
        
        # Чекаємо готовності Grafana з кількома спробами
        echo "Waiting for Grafana to be ready..."
        GRAFANA_READY=false
        for i in {1..12}; do
            if curl -s --connect-timeout 5 http://localhost:3000/api/health >/dev/null 2>&1; then
                echo "✅ Grafana is ready!"
                GRAFANA_READY=true
                break
            fi
            echo "⏳ Grafana not ready yet, attempt $i/12..."
            sleep 10
        done
        
        if [ "$GRAFANA_READY" = true ]; then
            # Імпортуємо всі доступні Ray дашборди
            echo "Importing all Ray dashboards..."
            DASHBOARDS_IMPORTED=0
            
            # Отримуємо список всіх дашбордів
            DASHBOARD_FILES=$(kubectl exec $HEAD_POD -c ray-head -- find $RAY_SESSION/metrics/grafana/dashboards/ -name "*.json" -type f 2>/dev/null || echo "")
            
            if [ ! -z "$DASHBOARD_FILES" ]; then
                for DASHBOARD_FILE in $DASHBOARD_FILES; do
                    DASHBOARD_NAME=$(basename $DASHBOARD_FILE .json)
                    echo "📊 Processing dashboard: $DASHBOARD_NAME"
                    
                    # Копіюємо dashboard
                    if kubectl cp $HEAD_POD:$DASHBOARD_FILE monitoring/grafana/${DASHBOARD_NAME}.json -c ray-head 2>/dev/null; then
                        # Перевіряємо JSON
                        if jq empty monitoring/grafana/${DASHBOARD_NAME}.json 2>/dev/null; then
                            # Імпортуємо через API
                            DASHBOARD_JSON=$(cat monitoring/grafana/${DASHBOARD_NAME}.json)
                            API_RESPONSE=$(curl -s -X POST http://localhost:3000/api/dashboards/db \
                                -u "admin:prom-operator" \
                                -H "Content-Type: application/json" \
                                -d "{
                                    \"dashboard\": $DASHBOARD_JSON,
                                    \"overwrite\": true,
                                    \"message\": \"Ray $DASHBOARD_NAME imported from live cluster\"
                                }" 2>/dev/null)
                            
                            if echo "$API_RESPONSE" | jq -e '.status == "success"' >/dev/null 2>&1; then
                                DASHBOARD_URL=$(echo "$API_RESPONSE" | jq -r '.url')
                                echo "  ✅ $DASHBOARD_NAME imported successfully!"
                                echo "  📊 URL: http://localhost:3000$DASHBOARD_URL"
                                DASHBOARDS_IMPORTED=$((DASHBOARDS_IMPORTED + 1))
                            else
                                echo "  ❌ Failed to import $DASHBOARD_NAME"
                            fi
                        else
                            echo "  ⚠️ Invalid JSON for $DASHBOARD_NAME"
                        fi
                    else
                        echo "  ⚠️ Failed to copy $DASHBOARD_NAME"
                    fi
                done
                
                echo "🎉 Successfully imported $DASHBOARDS_IMPORTED Ray dashboards!"
            else
                echo "⚠️ No dashboard files found"
            fi
        else
            echo "⚠️ Ray session not found in cluster"
        fi
    else
        echo "⚠️ Ray session not found in cluster"
    fi
else
    echo "❌ Head pod not found"
    exit 1
fi

echo "=== 10. Setting up port forwarding ==="
# Вбиваємо будь-які існуючі переадресації портів
pkill -f "kubectl port-forward.*raycluster-kuberay-head-svc" || true
pkill -f "kubectl port-forward.*prometheus-kube-prometheus-prometheus" || true

# Налаштовуємо переадресації портів у фоновому режимі
echo "Starting port forwards..."

# Ray services
kubectl port-forward service/raycluster-kuberay-head-svc 8265:8265 > /dev/null 2>&1 &
kubectl port-forward service/raycluster-kuberay-head-svc 10001:10001 > /dev/null 2>&1 &
kubectl port-forward service/raycluster-kuberay-head-svc 8000:8000 > /dev/null 2>&1 &

# Prometheus (Grafana port-forward вже налаштований раніше)
kubectl port-forward svc/prometheus-kube-prometheus-prometheus -n prometheus-system 9090:9090 > /dev/null 2>&1 &

# Чекаємо встановлення переадресацій портів
echo "Waiting for port forwards to establish..."
sleep 15

# Перевірка доступності
echo "Checking service availability..."
curl -s --connect-timeout 3 http://localhost:8265 > /dev/null && echo "✅ Ray Dashboard accessible" || echo "⚠️  Ray Dashboard may need more time to start"
curl -s --connect-timeout 3 http://localhost:9090 > /dev/null && echo "✅ Prometheus accessible" || echo "⚠️  Prometheus may need more time to start"
curl -s --connect-timeout 3 http://localhost:3000 > /dev/null && echo "✅ Grafana accessible" || echo "⚠️  Grafana may need more time to start"

echo "=== 11. Verifying metrics collection ==="
echo "Checking if Ray metrics are being collected..."
sleep 5

# Перевіряємо, чи Ray експортує метрики
RAY_METRICS_URL="http://localhost:8265/api/prometheus_metrics"
if curl -s --connect-timeout 5 "$RAY_METRICS_URL" | head -10 > /dev/null 2>&1; then
    echo "✅ Ray metrics endpoint is responding"
else
    echo "⚠️  Ray metrics endpoint may need more time to start"
fi

echo "=== Ray cluster with Prometheus and Grafana setup completed! ==="
echo ""
echo "🎉 Services available at:"
echo "   📊 Ray Dashboard:     http://localhost:8265"
echo "   📈 Prometheus:        http://localhost:9090"  
echo "   📊 Grafana:           http://localhost:3000"
echo "      Grafana login:     admin / prom-operator"

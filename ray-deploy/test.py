import cv2
import numpy as np
import requests
import json
import base64

image_path = "/Users/rmatusevych.appwell/Projects/mlops-homework-2/dataset/images/Boletus_edulis22.png"
server_url = "http://localhost:8000/detect"

# Load image from local path
image = cv2.imread(image_path)

if image is None:
    print(f"Error: Could not load image from {image_path}")
    exit(1)

# Encode image to base64 for sending to server
_, buffer = cv2.imencode('.png', image)
image_b64 = base64.b64encode(buffer).decode('utf-8')

# Send image data to server via POST request
resp = requests.post(server_url, json={"image_data": image_b64})
print(resp.json())

# Check if response is successful
if resp.status_code != 200:
    print(f"Error: Server returned status code {resp.status_code}")
    exit(1)

response_data = resp.json()

# Check if there's an error in the response
if "error" in response_data:
    print(f"Server error: {response_data['error']}")
    exit(1)

# Check if objects were detected
if "objects" in response_data:
    detections = response_data["objects"]
    
    for item in detections:
        class_name = item["class"]
        coords = item["coordinates"]

        cv2.rectangle(image, (int(coords[0]), int(coords[1])), (int(coords[2]), int(coords[3])), (0, 0, 0), 2)

        cv2.putText(image, class_name, (int(coords[0]), int(coords[1] - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

    cv2.imwrite("output.jpeg", image)
    print(f"Detection complete. Found {len(detections)} objects. Output saved to output.jpeg")
else:
    print("No objects detected in the image")
    cv2.imwrite("output.jpeg", image)
    print("Original image saved to output.jpeg")

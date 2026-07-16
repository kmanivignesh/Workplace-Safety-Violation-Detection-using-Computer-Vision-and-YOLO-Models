<div align="center">

# Workplace Safety Violation Detection

### Real-Time PPE & Smoking Violation Monitoring using Computer Vision and YOLO

**Python · Flask · OpenCV · PyTorch · Ultralytics YOLO**

</div>

---

## Overview

Workplace safety is a critical concern in high-risk industries such as **construction, manufacturing, warehousing, and mining**, where workers are routinely exposed to hazardous conditions. Manual monitoring — whether by on-site supervisors or passive CCTV review — is slow, labor-intensive, and prone to human error.

This project delivers an **end-to-end AI-powered safety monitoring system** that automatically detects Personal Protective Equipment (PPE) compliance and smoking violations in real time. It benchmarks three generations of YOLO object detection models (**YOLOv8, YOLOv9, YOLOv10**) and deploys the best-performing configuration through a **Flask web application** for live surveillance via webcam, image, or video input.

---

## Key Capabilities

| Category | Capability |
|---|---|
| **Detection** | Helmet compliance, safety vest compliance, smoking activity |
| **Input Modes** | Live webcam, image upload, video upload |
| **Alerts** | Real-time voice alerts on violation detection |
| **Logging** | Automatic violation logging with timestamped screenshots |
| **Reporting** | Downloadable detection reports |
| **Interface** | Interactive Flask web dashboard with bounding-box visualization |
| **Benchmarking** | Side-by-side comparison of YOLOv8, YOLOv9, and YOLOv10 |

---

## Project Structure

```text
CV_Application/
│
├── cv_app/                    # Core application logic
├── models/                    # Trained model weights
├── static/                    # Static assets (CSS, JS, images)
├── templates/                 # Flask HTML templates
├── utils/                     # Helper utilities
├── Video_testing/             # Video inference test scripts
├── app.py                     # Flask application entry point
├── requirements.txt           # Python dependencies
│
├── ppe/                        # PPE detection pipeline
│   ├── yolov8_ppe/
│   ├── yolov9_ppe/
│   ├── yolov10_ppe/
│   ├── data_analytics.ipynb
│   ├── dataset_analytics.csv
│   └── filtered.py
│
└── Smoking/                    # Smoking detection pipeline
    ├── Smoking_yolov8/
    ├── Smoking_Yolov9/
    ├── Smoking_Yolov10/
    ├── data_analytics.ipynb
    ├── preprocess.py
    └── preprocess2.py
```

---

## Tech Stack

| Layer | Tools |
|---|---|
| Language | Python |
| Web Framework | Flask |
| Computer Vision | OpenCV, Ultralytics YOLO |
| Deep Learning | PyTorch |
| Data Handling | NumPy, Pandas |
| Visualization | Matplotlib, PIL |
| Audio Alerts | pyttsx3 |

---

## Models Evaluated

| Task | Models Benchmarked |
|---|---|
| PPE Detection | YOLOv8s, YOLOv9c, YOLOv10m |
| Smoking Detection | YOLOv8n, YOLOv9c, YOLOv10 |

---

## Datasets

### PPE Detection Dataset

Annotated images of industrial workers, labeled for PPE compliance.

**Classes:** `Person` · `Helmet` · `Safety Vest`

| Split | Images |
|---|---:|
| Training | 2,991 |
| Validation | 119 |
| Test | 90 |
| **Total** | **3,200** |

**Source:** Construction PPE Detection Dataset (Roboflow Universe)

### Smoking Detection Dataset

Annotated images spanning varied environments and lighting conditions.

**Classes:** `Smoking`

| Split | Images |
|---|---:|
| Training | 3,378 |
| Validation | 592 |
| Test | 253 |
| **Total** | **4,223** |

**Source:** Smoking Detection Dataset (Roboflow Universe)

### Augmentation Strategy

To improve generalization and robustness, the following augmentations were applied during training:

- Mosaic
- MixUp
- HSV color-space augmentation
- Horizontal flip
- Scaling & translation
- Perspective transformation

---

## Training Configuration

| Parameter | PPE Detection | Smoking Detection |
|---|---|---|
| Models | YOLOv8s, YOLOv9c, YOLOv10m | YOLOv8n, YOLOv9c, YOLOv10 |
| Epochs | 100 | 100 |
| Image Size | 768 | 640 |
| Batch Size | 16 | 16 |
| Optimizer | AdamW | AdamW |
| Learning Rate | 0.001 | 0.001 |

---

## Model Performance

### PPE Detection

| Model | Precision | Recall | mAP@50 | mAP@50-95 |
|---|---:|---:|---:|---:|
| YOLOv8s | 86.2% | 80.8% | 85.7% | 34.4% |
| **YOLOv9c** | **86.3%** | **82.7%** | **86.8%** | **38.3%** |
| YOLOv10m | 89.5% | 75.7% | 87.8% | 42.9% |

**Best Overall Model:** `YOLOv9c` — selected for the strongest balance of precision, recall, and mAP@50.

### Smoking Detection

| Model | Precision | Recall | mAP@50 | mAP@50-95 |
|---|---:|---:|---:|---:|
| YOLOv8n | 39.6% | 47.6% | 36.2% | 18.2% |
| **YOLOv9c** | **58.9%** | **63.9%** | **55.6%** | **26.9%** |
| YOLOv10 | 42.6% | 56.5% | 40.3% | 18.0% |

**Best Overall Model:** `YOLOv9c` — outperforms both alternatives across every metric.

---

## Rule-Based PPE Verification

Rather than training separate **"No Helmet"** and **"No Vest"** classes — which would worsen class imbalance — the system applies lightweight rule-based logic on top of raw detections:

1. `Person` detected **without** `Helmet` → **Helmet Violation**
2. `Person` detected **without** `Safety Vest` → **Safety Vest Violation**
3. `Smoking` detected → **Smoking Violation**

This design choice keeps the underlying detector stable and avoids the noisy, imbalanced labels that dedicated "violation" classes would introduce.

---

## Flask Web Application

The dashboard provides a complete monitoring workflow:

- Live webcam monitoring
- Image upload & inference
- Video upload & inference
- Real-time bounding-box visualization
- Voice alerts on violation
- Automated violation logging
- Screenshot capture on detection
- Downloadable detection reports

---

## Installation & Usage

```bash
# 1. Clone the repository
git clone https://github.com/your-username/Workplace-Safety-Violation-Detection.git

# 2. Navigate into the project directory
cd Workplace-Safety-Violation-Detection

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python app.py
```

The dashboard will be available at `http://localhost:5000` (default Flask port).

---

## Future Improvements

- Multi-camera CCTV monitoring
- Worker tracking & re-identification
- Cloud-based dashboard
- Edge AI deployment (Jetson / Coral)
- Fire and hazard detection
- Safety gloves detection
- Safety goggles detection
- Safety boots detection
- Improved small-object detection
- Mobile application integration

---

## License

This project is intended for **educational and research purposes only**.

---

<div align="center">

*Built with for safer workplaces.*

</div>

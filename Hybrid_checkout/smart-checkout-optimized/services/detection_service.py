import cv2
import numpy as np
from ultralytics import YOLO
from typing import List, Dict, Optional
import asyncio
from pathlib import Path

class DetectionService:
    def __init__(self, db):
        self.db = db
        self.models = {}
        self.confidence_threshold = 0.6
        self.initialized = False
    
    async def initialize(self):
        model_dir = Path("models")
        
        model_files = {
            "chips": model_dir / "chips_model.pt",
            "drinks": model_dir / "drinks_model.pt",
            "general": model_dir / "general_model.pt"
        }
        
        for category, model_path in model_files.items():
            if model_path.exists():
                try:
                    print(f"Loading {category} model...")
                    self.models[category] = YOLO(str(model_path))
                    print(f"✓ {category} model loaded")
                except Exception as e:
                    print(f"✗ Error loading {category} model: {e}")
            else:
                print(f"⚠ {category} model not found at {model_path}")
        
        if not self.models:
            print("\n⚠️  No YOLO models found! Detection won't work.")
            print("   Add your models to the 'models' directory")
        
        self.initialized = True
        print(f"\nDetection service ready with {len(self.models)} models")
    
    async def detect_frame(self, frame: np.ndarray) -> List[Dict]:
        if not self.initialized or not self.models:
            return []
        
        detections = []
        
        for category, model in self.models.items():
            try:
                results = model(frame, conf=self.confidence_threshold, verbose=False)
                
                for r in results:
                    if hasattr(r, 'boxes') and r.boxes is not None:
                        for box in r.boxes:
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            conf = box.conf[0].item()
                            cls = int(box.cls[0].item())
                            class_name = model.names[cls]
                            
                            product = self.db.get_product_by_yolo_class(class_name)
                            
                            detection = {
                                "bbox": {
                                    "x1": int(x1),
                                    "y1": int(y1),
                                    "x2": int(x2),
                                    "y2": int(y2)
                                },
                                "confidence": float(conf),
                                "class_name": class_name,
                                "category": category,
                                "product": product
                            }
                            detections.append(detection)
            
            except Exception as e:
                print(f"Detection error in {category}: {e}")
        
        return detections

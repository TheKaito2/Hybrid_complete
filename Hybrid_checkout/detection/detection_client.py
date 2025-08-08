# DEBUG VERSION - YOLO DETECTION CLIENT
# This version will help us see what's happening with your models

import cv2
import numpy as np
from ultralytics import YOLO
import requests
import json
import time
from pathlib import Path

class MinimalDetectionClient:
    def __init__(self):
        # API Configuration
        self.api_base_url = "http://localhost:8000"
        
        # Load your trained YOLO models
        self.models = {}
        self.load_models()
        
        # Detection settings - try lower threshold first
        self.confidence_threshold = 0.3  # Lowered to detect more
        
        # Camera setup
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        # Product mapping: YOLO class name -> web database ID
        # Your YOLO outputs: "Lay's-Flat-Original-Flavor" (with apostrophe and -Flavor suffix)
        # Your web expects: "lays-flat-original" (no apostrophe, no suffix)
        self.products = {
            # Chips - EXACT YOLO names from your model
            "Lay's-Flat-Original-Flavor": {"web_id": "lays-flat-original", "price": 20.0},
            "Lay's-Nori-Seaweed-Flavor": {"web_id": "lays-nori-seaweed", "price": 25.0},
            "Lay's-Ridged-Original-Flavor": {"web_id": "lays-ridged-original", "price": 22.0},
            "Snackjack-Original-Flavor": {"web_id": "snackjack-original", "price": 18.0},
            "Tasto-Japanese-Seaweed-Flavor": {"web_id": "tasto-japanese-seaweed", "price": 24.0},
            "Tasto-Original-Flavor": {"web_id": "tasto-original", "price": 22.0},
            "Enter": {"web_id": "enter", "price": 18.0},
            "Atreus": {"web_id": "atreus", "price": 22.0},
            
            # Drinks - EXACT YOLO names
            "CocaCola-Bottle": {"web_id": "coca-cola-bottle", "price": 18.0},
            "CocaCola-Can": {"web_id": "coca-cola-can", "price": 14.0},
            "Crystal-Water": {"web_id": "crystal-water", "price": 7.0},
            "Fanta-FruitPunch-Flavor": {"web_id": "fanta-fruit-punch", "price": 14.0},
            "Pepsi": {"web_id": "pepsi", "price": 14.0},
            "Sprite": {"web_id": "sprite", "price": 14.0}
        }
        
        # Track detections
        self.current_detections = []
        self.debug_mode = True  # Enable debug output
        
    def load_models(self):
        """Load your trained YOLO models and show what classes they contain"""
        model_paths = {
            'chips': 'trained_models/chips_model.pt',
            'drinks': 'trained_models/drinks_model.pt',
        }
        
        print("\n" + "="*60)
        print("LOADING YOLO MODELS")
        print("="*60)
        
        for category, path in model_paths.items():
            if Path(path).exists():
                print(f"\n✓ Loading {category} model from {path}")
                try:
                    model = YOLO(path)
                    self.models[category] = model
                    
                    # IMPORTANT: Show what classes this model knows
                    print(f"  Model has {len(model.names)} classes:")
                    for idx, name in model.names.items():
                        print(f"    Class {idx}: {name}")
                    
                except Exception as e:
                    print(f"✗ Error loading {category} model: {e}")
            else:
                print(f"\n⚠ {category} model not found at {path}")
                print(f"  Please copy your {category}_model.pt to 'trained_models/' folder")
        
        if not self.models:
            print("\n" + "="*60)
            print("⚠️  NO MODELS FOUND!")
            print("="*60)
            print("\nPlease ensure your model files are in the 'trained_models/' folder:")
            print("  - trained_models/chips_model.pt")
            print("  - trained_models/drinks_model.pt")
            print("\nIf your models are elsewhere, copy them with:")
            print("  mkdir trained_models")
            print("  cp /path/to/your/chips_model.pt trained_models/")
            print("  cp /path/to/your/drinks_model.pt trained_models/")
        else:
            print("\n" + "="*60)
            print(f"✓ Successfully loaded {len(self.models)} models")
            print("="*60)
    
    def detect_products(self, frame):
        """Run detection on current frame with debug info"""
        detections = []
        
        for category, model in self.models.items():
            try:
                # Run detection with verbose output first time
                verbose = self.debug_mode
                results = model(frame, conf=self.confidence_threshold, verbose=verbose)
                
                # Turn off verbose after first detection
                if verbose:
                    self.debug_mode = False
                
                for r in results:
                    if hasattr(r, 'boxes') and r.boxes is not None and len(r.boxes) > 0:
                        print(f"\n📦 {category} model found {len(r.boxes)} objects!")
                        
                        for box in r.boxes:
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            conf = box.conf[0].item()
                            cls = int(box.cls[0].item())
                            class_name = model.names[cls]
                            
                            print(f"  - Detected: {class_name} (confidence: {conf:.2f})")
                            
                            # Check if we know this product
                            if class_name in self.products:
                                product_info = self.products[class_name]
                                print(f"    ✓ Found in database: ฿{product_info['price']}")
                            else:
                                print(f"    ⚠ NOT in product database - add this product name!")
                                # Add unknown product with default values
                                product_info = {"web_id": class_name.lower().replace(" ", "-"), "price": 10.0}
                            
                            detection = {
                                'bbox': [int(x1), int(y1), int(x2), int(y2)],
                                'confidence': float(conf),
                                'class_name': class_name,
                                'category': category,
                                'price': product_info['price'],
                                'web_id': product_info.get('web_id', class_name.lower().replace(" ", "-"))
                            }
                            detections.append(detection)
                            
            except Exception as e:
                print(f"✗ Detection error in {category}: {e}")
        
        return detections
    
    def draw_detections(self, frame, detections):
        """Draw bounding boxes and info on frame"""
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            conf = det['confidence']
            name = det['class_name']
            price = det['price']
            
            # Choose color based on confidence
            if conf > 0.7:
                color = (0, 255, 0)  # Green - high confidence
            elif conf > 0.5:
                color = (0, 255, 255)  # Yellow - medium
            else:
                color = (0, 165, 255)  # Orange - low
            
            # Draw box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Draw label background
            label_text = f"{name} ฿{price:.0f} ({conf*100:.0f}%)"
            label_size = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(frame, (x1, y1-30), (x1+label_size[0]+10, y1), color, -1)
            
            # Draw text
            cv2.putText(frame, label_text, (x1+5, y1-8), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        
        return frame
    
    def test_detection(self):
        """Test detection on a single frame"""
        print("\n" + "="*60)
        print("TESTING DETECTION")
        print("="*60)
        print("Taking a test photo in 3 seconds...")
        print("Please place a product in front of the camera!")
        
        for i in range(3, 0, -1):
            print(f"  {i}...")
            time.sleep(1)
        
        ret, frame = self.cap.read()
        if ret:
            print("\n📷 Captured frame, running detection...")
            detections = self.detect_products(frame)
            
            if detections:
                print(f"\n✅ SUCCESS! Detected {len(detections)} items")
            else:
                print("\n❌ No detections found. Possible issues:")
                print("  1. Product not in camera view")
                print("  2. Confidence threshold too high (currently {:.1f})".format(self.confidence_threshold))
                print("  3. Model not trained on this product")
                print("  4. Lighting conditions different from training")
                
                # Save frame for debugging
                cv2.imwrite("debug_frame.jpg", frame)
                print("\n💾 Saved current frame as 'debug_frame.jpg' for inspection")
    
    def send_to_cart(self, detections):
        """Send detected items to web cart via API"""
        if not detections:
            return False
        
        success_count = 0
        failed_count = 0
        
        # Send each item individually to match your API format
        for det in detections:
            try:
                class_name = det['class_name']
                
                # Get the web product ID from our mapping
                if class_name in self.products:
                    product_id = self.products[class_name]['web_id']
                else:
                    # Fallback: try to auto-format the name
                    product_id = class_name.lower().replace(" ", "-").replace("'", "")
                    print(f"⚠ Unknown product '{class_name}', using auto-formatted ID: {product_id}")
                
                # Send to your Flask API endpoint
                print(f"Sending {class_name} as {product_id}...")
                response = requests.post(
                    f"{self.api_base_url}/api/add-to-cart",
                    json={
                        "product_id": product_id,
                        "quantity": 1
                    },
                    timeout=5
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✓ Added {class_name} to web cart")
                    success_count += 1
                else:
                    print(f"✗ Failed to add {class_name}: HTTP {response.status_code}")
                    try:
                        error = response.json()
                        print(f"  Error: {error.get('error', 'Unknown error')}")
                    except:
                        print(f"  Response: {response.text}")
                    failed_count += 1
                    
            except requests.exceptions.ConnectionError:
                print("✗ Cannot connect to web cart - Is Flask server running on localhost:8000?")
                failed_count += 1
                break
            except Exception as e:
                print(f"✗ Error sending {det['class_name']}: {e}")
                failed_count += 1
        
        if success_count > 0:
            print(f"\n📦 Summary: {success_count} added, {failed_count} failed")
            return True
        else:
            print(f"\n❌ Failed to add any items to cart")
            return False
    
    def run(self):
        """Main detection loop"""
        print("\n" + "="*60)
        print("YOLO DETECTION CLIENT - DEBUG MODE")
        print("="*60)
        
        # First, test detection
        self.test_detection()
        
        print("\n" + "="*60)
        print("STARTING LIVE DETECTION")
        print("="*60)
        print("\nControls:")
        print("  SPACE - Capture & send to cart")
        print("  T     - Test detection (debug)")
        print("  C     - Clear detections")
        print("  +/-   - Adjust confidence threshold")
        print("  Q     - Quit")
        print(f"\nCurrent confidence threshold: {self.confidence_threshold:.1f}")
        print("\n")
        
        frame_count = 0
        fps_time = time.time()
        fps = 0
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to grab frame")
                break
            
            # Calculate FPS
            frame_count += 1
            if frame_count % 30 == 0:
                fps = 30 / (time.time() - fps_time)
                fps_time = time.time()
            
            # Run detection every few frames for performance
            if frame_count % 10 == 0:  # Detect every 10th frame
                self.current_detections = self.detect_products(frame)
            
            # Draw detections
            display_frame = self.draw_detections(frame.copy(), self.current_detections)
            
            # Add status overlay
            status_text = f"FPS: {fps:.1f} | Detecting: {len(self.current_detections)} | Threshold: {self.confidence_threshold:.1f}"
            cv2.putText(display_frame, status_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            instructions = "SPACE: Send to cart | T: Test | +/-: Threshold | Q: Quit"
            cv2.putText(display_frame, instructions, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            
            # Show frame
            cv2.imshow('YOLO Detection - Debug Mode', display_frame)
            
            # Handle keyboard
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
            elif key == ord(' '):  # SPACE - Send to cart
                if self.current_detections:
                    print(f"\n📷 Sending {len(self.current_detections)} items to cart...")
                    self.send_to_cart(self.current_detections)
                else:
                    print("\n⚠ No items detected")
            elif key == ord('t'):  # Test detection
                self.test_detection()
            elif key == ord('c'):  # Clear
                self.current_detections = []
                print("\nCleared detections")
            elif key == ord('+') or key == ord('='):  # Increase threshold
                self.confidence_threshold = min(0.9, self.confidence_threshold + 0.1)
                print(f"\nConfidence threshold: {self.confidence_threshold:.1f}")
            elif key == ord('-'):  # Decrease threshold
                self.confidence_threshold = max(0.1, self.confidence_threshold - 0.1)
                print(f"\nConfidence threshold: {self.confidence_threshold:.1f}")
        
        # Cleanup
        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    print("="*60)
    print("YOLO DETECTION CLIENT - STARTUP")
    print("="*60)
    
    # Create required directories
    Path("trained_models").mkdir(exist_ok=True)
    
    # Check for Flask server
    try:
        response = requests.get("http://localhost:8000", timeout=2)
        print("✓ Flask server detected on localhost:8000")
    except:
        print("⚠ Flask server not running on localhost:8000")
        print("  Detection will work but cart sending will fail")
    
    # Run the client
    client = MinimalDetectionClient()
    client.run()
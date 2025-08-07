from ultralytics import YOLO
import cv2
import threading
import time
from typing import List, Dict, Optional, Tuple, Callable
from pathlib import Path


class VideoStream:
    """Threaded camera class for efficient video capture"""
    
    def __init__(self, src):
        """
        Initialize video stream
        
        Args:
            src: Camera source (int for webcam or string for IP camera)
        """
        self.cap = cv2.VideoCapture(0)
        self.ret, self.frame = self.cap.read()
        self.stopped = False
        self.lock = threading.Lock()
        
        # Start update thread
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()
    
    def update(self):
        """Continuously update frames in background thread"""
        while not self.stopped:
            ret, frame = self.cap.read()
            with self.lock:
                self.ret, self.frame = ret, frame
            time.sleep(0.01)
    
    def read(self):
        """Get the current frame"""
        with self.lock:
            return self.ret, self.frame.copy() if self.frame is not None else (False, None)
    
    def stop(self):
        """Stop the video stream"""
        self.stopped = True
        self.thread.join()
        self.cap.release()


class YOLODetector:
    """YOLO detection system wrapper"""
    
    def __init__(self, model_paths: Dict[str, str], conf_threshold: float = 0.5):
        """
        Initialize YOLO detector with multiple models
        
        Args:
            model_paths: Dictionary of category -> model path
            conf_threshold: Confidence threshold for detections
        """
        self.models = {}
        self.conf_threshold = conf_threshold
        self.last_detections = []
        self.detection_callback = None
        
        # Load models
        for category, path in model_paths.items():
            if Path(path).exists():
                print(f"Loading {category} model from {path}")
                self.models[category] = YOLO(path)
            else:
                print(f"Warning: Model not found at {path}")
    
    def detect(self, frame, input_size: int = 416) -> List[Dict]:
        """
        Run detection on a frame
        
        Args:
            frame: Input frame
            input_size: Model input size
            
        Returns:
            List of detections with format:
            {
                'class_name': str,
                'confidence': float,
                'bbox': (x1, y1, x2, y2),
                'category': str
            }
        """
        if not frame.size:
            return []
        
        # Resize frame for faster detection
        resized = cv2.resize(frame, (input_size, input_size))
        
        # Scale factors for mapping back to original size
        scale_x = frame.shape[1] / input_size
        scale_y = frame.shape[0] / input_size
        
        detections = []
        
        # Run detection with each model
        for category, model in self.models.items():
            try:
                # Run inference with higher confidence and lower IOU for NMS
                results = model(resized, show=False, verbose=False, conf=self.conf_threshold, iou=0.5)[0]
                
                if hasattr(results, 'boxes') and results.boxes is not None:
                    for result in results.boxes.data.tolist():
                        x1, y1, x2, y2, score, cls_id = result
                        
                        if score >= self.conf_threshold:
                            # Scale coordinates back to original frame size
                            x1 = int(x1 * scale_x)
                            y1 = int(y1 * scale_y)
                            x2 = int(x2 * scale_x)
                            y2 = int(y2 * scale_y)
                            
                            detection = {
                                'class_name': model.names[int(cls_id)],
                                'confidence': score,
                                'bbox': (x1, y1, x2, y2),
                                'category': category
                            }
                            detections.append(detection)
                        
            except Exception as e:
                print(f"Error in {category} detection: {e}")
        
        # Remove duplicate/overlapping detections
        detections = self._filter_overlapping_detections(detections)
        
        self.last_detections = detections
        
        # Call callback if set
        if self.detection_callback:
            self.detection_callback(detections)
        
        return detections
    
    def _filter_overlapping_detections(self, detections: List[Dict], iou_threshold: float = 0.5) -> List[Dict]:
        """
        Filter overlapping detections using IoU (Intersection over Union)
        
        Args:
            detections: List of detections
            iou_threshold: IoU threshold for considering boxes as duplicates
            
        Returns:
            Filtered list of detections
        """
        if not detections:
            return []
        
        # Sort by confidence
        detections = sorted(detections, key=lambda x: x['confidence'], reverse=True)
        
        filtered = []
        for detection in detections:
            # Check if this detection overlaps with any already selected
            is_duplicate = False
            for selected in filtered:
                if self._calculate_iou(detection['bbox'], selected['bbox']) > iou_threshold:
                    # If same class, it's a duplicate
                    if detection['class_name'] == selected['class_name']:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                filtered.append(detection)
        
        return filtered
    
    def _calculate_iou(self, box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
        """
        Calculate Intersection over Union (IoU) between two boxes
        
        Args:
            box1: (x1, y1, x2, y2)
            box2: (x1, y1, x2, y2)
            
        Returns:
            IoU value between 0 and 1
        """
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        
        # Calculate intersection area
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i < x1_i or y2_i < y1_i:
            return 0.0
        
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        
        # Calculate union area
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def draw_detections(self, frame, detections: List[Dict]) -> None:
        """
        Draw detection boxes on frame
        
        Args:
            frame: Frame to draw on
            detections: List of detections
        """
        # Define colors for different categories
        colors = {
            'chips': (0, 255, 255),  # Yellow
            'drinks': (0, 0, 255),   # Red
            'default': (0, 255, 0)   # Green
        }
        
        for detection in detections:
            x1, y1, x2, y2 = detection['bbox']
            category = detection['category']
            color = colors.get(category, colors['default'])
            
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label = f"{detection['class_name']} {detection['confidence']:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            
            # Draw label background
            cv2.rectangle(frame, 
                         (x1, y1 - label_size[1] - 10),
                         (x1 + label_size[0], y1),
                         color, -1)
            
            # Draw label text
            cv2.putText(frame, label,
                       (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX,
                       0.5, (255, 255, 255), 2)
    
    def set_detection_callback(self, callback: Callable):
        """Set callback function for new detections"""
        self.detection_callback = callback
    
    def get_unique_products(self, detections: List[Dict]) -> List[str]:
        """
        Get unique product class names from detections
        
        Args:
            detections: List of detections
            
        Returns:
            List of unique class names
        """
        return list(set(d['class_name'] for d in detections))


class DetectionDebouncer:
    """Debounce detections to avoid duplicate scans"""
    
    def __init__(self, debounce_time: float = 1.0):
        """
        Initialize debouncer
        
        Args:
            debounce_time: Time in seconds to wait before allowing same detection
        """
        self.debounce_time = debounce_time
        self.last_detections = {}
        self.lock = threading.Lock()
    
    def is_new_detection(self, class_name: str) -> bool:
        """
        Check if detection is new (not recently detected)
        
        Args:
            class_name: Detected class name
            
        Returns:
            True if new detection, False if recently detected
        """
        current_time = time.time()
        
        with self.lock:
            if class_name in self.last_detections:
                time_diff = current_time - self.last_detections[class_name]
                if time_diff < self.debounce_time:
                    return False
            
            self.last_detections[class_name] = current_time
            return True
    
    def clear(self):
        """Clear all detection history"""
        with self.lock:
            self.last_detections.clear()

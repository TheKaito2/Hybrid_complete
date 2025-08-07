import sys
import json
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import cv2
import numpy as np
import requests
import logging
from datetime import datetime

from models.product import Product
from models.cart import ShoppingCart
from models.database_manager import DatabaseManager
from detection.yolo_detector import YOLODetector, VideoStream, DetectionDebouncer

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CameraWidget(QWidget):
    """Widget for displaying camera feed and detections"""
    
    products_detected = pyqtSignal(list)  # Emitted when products are detected
    
    def __init__(self, detector: YOLODetector, video_stream: VideoStream):
        super().__init__()
        self.detector = detector
        self.video_stream = video_stream
        self.current_frame = None
        
        # UI setup
        self.setup_ui()
        
        # Set widget background
        self.setStyleSheet("""
            CameraWidget {
                background-color: #2A2A2A;
            }
        """)
        
        # Timer for updating camera feed
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)  # 30ms = ~33 FPS
    
    def setup_ui(self):
        """Setup camera widget UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Camera display
        self.camera_label = QLabel()
        self.camera_label.setMinimumSize(640, 480)
        self.camera_label.setScaledContents(True)
        self.camera_label.setStyleSheet("""
            QLabel {
                border: 2px solid #4ECDC4;
                border-radius: 10px;
                background-color: #2A2A2A;
            }
        """)
        
        layout.addWidget(self.camera_label)
        self.setLayout(layout)
    
    def capture_and_detect(self):
        """Capture current frame and detect products"""
        if self.current_frame is not None:
            logger.info("Capturing frame for detection...")
            # Run detection on current frame
            detections = self.detector.detect(self.current_frame)
            
            # Flash effect
            self.flash_effect()
            
            if detections:
                logger.info(f"Found {len(detections)} products in snapshot")
                self.products_detected.emit(detections)
            else:
                logger.info("No products detected in snapshot")
            
            return detections
        return []
    
    def flash_effect(self):
        """Create camera flash effect"""
        # White flash overlay
        white_pixmap = QPixmap(self.camera_label.size())
        white_pixmap.fill(Qt.white)
        self.camera_label.setPixmap(white_pixmap)
        
        # Play sound if available
        QApplication.beep()
        
        # Return to normal after 100ms
        QTimer.singleShot(100, self.update_frame)
    
    def update_frame(self):
        """Update camera frame"""
        ret, frame = self.video_stream.read()
        if ret and frame is not None:
            self.current_frame = frame.copy()
            
            # Always run detection for visualization
            detections = self.detector.detect(frame)
            
            # Draw detection boxes on frame
            self.detector.draw_detections(frame, detections)
            
            # Convert to Qt format and display
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            
            # Scale to fit label
            scaled_pixmap = pixmap.scaled(self.camera_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.camera_label.setPixmap(scaled_pixmap)


class CartItemWidget(QWidget):
    """Custom widget for cart items with delete button"""
    
    delete_clicked = pyqtSignal(str)  # product_id
    
    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.item = item
        self.setup_ui()
    
    def setup_ui(self):
        # Set widget background
        self.setStyleSheet("""
            CartItemWidget {
                background-color: #3A3A3A;
                border-radius: 8px;
                margin: 3px;
                border: 1px solid #555555;
            }
            CartItemWidget:hover {
                border: 1px solid #FF6B35;
            }
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        
        # Icon label
        icon_label = QLabel("🛒")
        icon_label.setStyleSheet("font-size: 20px; background-color: transparent;")
        layout.addWidget(icon_label)
        
        # Item info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        name_label = QLabel(self.item.product.name)
        name_label.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: bold; background-color: transparent;")
        
        detail_label = QLabel(f"฿{self.item.product.price:.2f} × {self.item.quantity} = ฿{self.item.subtotal:.2f}")
        detail_label.setStyleSheet("color: #FF6B35; font-size: 14px; background-color: transparent;")
        
        info_layout.addWidget(name_label)
        info_layout.addWidget(detail_label)
        
        # Delete button
        delete_btn = QPushButton("🗑️")
        delete_btn.setFixedSize(32, 32)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border-radius: 16px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
            QPushButton:pressed {
                background-color: #B71C1C;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.item.product.id))
        
        layout.addLayout(info_layout)
        layout.addStretch()
        layout.addWidget(delete_btn)
        
        self.setLayout(layout)


class CartWidget(QWidget):
    """Widget for displaying shopping cart"""
    
    checkout_clicked = pyqtSignal()
    
    def __init__(self, cart: ShoppingCart):
        super().__init__()
        self.cart = cart
        self.setup_ui()
        
        # Set widget background
        self.setStyleSheet("""
            CartWidget {
                background-color: #2A2A2A;
            }
        """)
        
        # Show initial empty state
        self.update_cart_display()
    
    def setup_ui(self):
        """Setup cart widget UI"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title = QLabel("Local Preview")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #FFFFFF;
                padding: 10px;
                background-color: transparent;
            }
        """)
        layout.addWidget(title)
        
        # Info label
        info_label = QLabel("Items will be sent to web cart")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #999999;
                padding: 5px;
                background-color: transparent;
            }
        """)
        layout.addWidget(info_label)
        
        # Cart items label
        items_label = QLabel("Preview Items:")
        items_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #FF6B35;
                padding: 5px;
                background-color: transparent;
                font-weight: bold;
            }
        """)
        layout.addWidget(items_label)
        
        # Cart items list
        self.items_widget = QWidget()
        self.items_widget.setStyleSheet("background-color: #2A2A2A;")
        self.items_layout = QVBoxLayout()
        self.items_layout.setSpacing(5)
        self.items_layout.setContentsMargins(5, 5, 5, 5)
        self.items_widget.setLayout(self.items_layout)
        
        # Scroll area for items
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.items_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(200)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #2A2A2A;
                border: 2px solid #FF6B35;
                border-radius: 10px;
                padding: 5px;
            }
            QScrollBar:vertical {
                background-color: #3A3A3A;
                width: 12px;
                border-radius: 6px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background-color: #FF6B35;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #FF5722;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)
        layout.addWidget(scroll_area, 1)  # Give it stretch factor
        
        # Summary section
        summary_widget = QWidget()
        summary_layout = QVBoxLayout()
        summary_widget.setStyleSheet("""
            QWidget {
                background-color: #2A2A2A;
                border: 1px solid #FF6B35;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        
        # Subtotal
        self.subtotal_label = QLabel("Subtotal: ฿0.00")
        self.subtotal_label.setStyleSheet("font-size: 18px; color: #FFFFFF;")
        summary_layout.addWidget(self.subtotal_label)
        
        # Tax
        self.tax_label = QLabel("Tax: ฿0.00")
        self.tax_label.setStyleSheet("font-size: 18px; color: #FF6B35;")
        summary_layout.addWidget(self.tax_label)
        
        # Total
        self.total_label = QLabel("Total: ฿0.00")
        self.total_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #FFFFFF;")
        summary_layout.addWidget(self.total_label)
        
        summary_widget.setLayout(summary_layout)
        layout.addWidget(summary_widget)


        # Note
        note_label = QLabel("📌 This is local preview only\nActual cart is on web interface")
        note_label.setAlignment(Qt.AlignCenter)
        note_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 11px;
                padding: 10px;
                background-color: #333333;
                border-radius: 5px;
                margin: 5px;
            }
        """)
        layout.addWidget(note_label)
        
        self.setLayout(layout)
    
    def update_cart_display(self):
        """Update cart display with current items"""
        # Clear existing items
        while self.items_layout.count():
            child = self.items_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Add cart items
        for item in self.cart.get_items():
            item_widget = CartItemWidget(item)
            item_widget.delete_clicked.connect(self.on_delete_item)
            self.items_layout.addWidget(item_widget)
        
        # Add empty state if no items
        if len(self.cart) == 0:
            empty_label = QLabel("Preview empty Scanned items appear here")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("""
                QLabel {
                    color: #666666;
                    font-size: 14px;
                    padding: 20px;
                    background-color: transparent;
                }
            """)
            self.items_layout.addWidget(empty_label)
        
        # Add stretch at the end
        self.items_layout.addStretch()
        
        # Update summary
        summary = self.cart.get_summary()
        self.subtotal_label.setText(f"Subtotal: ฿{summary['subtotal']:.2f}")
        self.tax_label.setText(f"Tax: ฿{summary['tax']:.2f}")
        self.total_label.setText(f"Total: ฿{summary['total']:.2f}")
    
    def on_delete_item(self, product_id):
        """Handle item deletion"""
        self.cart.remove_product(product_id)
        self.update_cart_display()


class DetectedItemWidget(QWidget):
    """Custom widget for detected items with delete button"""
    
    delete_clicked = pyqtSignal(int)  # index
    
    def __init__(self, product, index, parent=None):
        super().__init__(parent)
        self.product = product
        self.index = index
        self.setup_ui()
    
    def setup_ui(self):
        # Set widget background
        self.setStyleSheet("""
            DetectedItemWidget {
                background-color: #3A3A3A;
                border-radius: 8px;
                margin: 3px;
                border: 1px solid #555555;
            }
            DetectedItemWidget:hover {
                border: 1px solid #4ECDC4;
            }
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        
        # Icon label
        icon_label = QLabel("📦")
        icon_label.setStyleSheet("font-size: 20px; background-color: transparent;")
        layout.addWidget(icon_label)
        
        # Item info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        name_label = QLabel(self.product.name)
        name_label.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: bold; background-color: transparent;")
        
        price_label = QLabel(f"฿{self.product.price:.2f}")
        price_label.setStyleSheet("color: #4ECDC4; font-size: 14px; background-color: transparent;")
        
        info_layout.addWidget(name_label)
        info_layout.addWidget(price_label)
        
        # Delete button
        delete_btn = QPushButton("✕")
        delete_btn.setFixedSize(28, 28)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border-radius: 14px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
            QPushButton:pressed {
                background-color: #B71C1C;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.index))
        
        layout.addLayout(info_layout)
        layout.addStretch()
        layout.addWidget(delete_btn)
        
        self.setLayout(layout)


class ScannerWidget(QWidget):
    """Central scanner widget with scan button and detected items"""
    
    add_to_cart_clicked = pyqtSignal()
    scan_clicked = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.detected_products = []
        self.setup_ui()
        
        # Set widget background
        self.setStyleSheet("""
            ScannerWidget {
                background-color: #2A2A2A;
            }
        """)
        
        # Show initial empty state
        self.refresh_display()
    
    def setup_ui(self):
        """Setup scanner widget UI"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title = QLabel("Scanner Control")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #FFFFFF;
                padding: 10px;
                background-color: transparent;
            }
        """)
        layout.addWidget(title)
        
        # Scan button
        self.scan_button = QPushButton("📷 SCAN PRODUCTS")
        self.scan_button.setStyleSheet("""
            QPushButton {
                background-color: #4ECDC4;
                color: white;
                font-size: 28px;
                font-weight: bold;
                padding: 20px;
                border-radius: 15px;
                border: none;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #45B7AA;
                transform: scale(1.02);
            }
            QPushButton:pressed {
                background-color: #3A9B8F;
                transform: scale(0.98);
            }
        """)
        self.scan_button.clicked.connect(self.scan_clicked.emit)
        layout.addWidget(self.scan_button)
        
        # Detected items label
        detected_label = QLabel("Detected Items:")
        detected_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #4ECDC4;
                padding: 5px;
                background-color: transparent;
                font-weight: bold;
            }
        """)
        layout.addWidget(detected_label)
        
        # Detected items widget
        self.detected_widget = QWidget()
        self.detected_widget.setStyleSheet("background-color: #2A2A2A;")
        self.detected_layout = QVBoxLayout()
        self.detected_layout.setSpacing(5)
        self.detected_layout.setContentsMargins(5, 5, 5, 5)
        self.detected_widget.setLayout(self.detected_layout)
        
        # Scroll area for detected items
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.detected_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(200)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #2A2A2A;
                border: 2px solid #4ECDC4;
                border-radius: 10px;
                padding: 5px;
            }
            QScrollBar:vertical {
                background-color: #3A3A3A;
                width: 12px;
                border-radius: 6px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background-color: #4ECDC4;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #45B7AA;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)
        layout.addWidget(scroll_area, 1)  # Give it stretch factor
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        # Clear button
        self.clear_button = QPushButton("🗑️ Clear")
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                color: white;
                font-size: 18px;
                font-weight: bold;
                padding: 12px;
                border-radius: 10px;
                border: none;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #666666;
            }
        """)
        self.clear_button.clicked.connect(self.clear_detected)
        self.clear_button.setEnabled(False)
        buttons_layout.addWidget(self.clear_button)
        
        # Add button
        self.add_button = QPushButton("🌐 SEND TO WEB CART")
        self.add_button.setStyleSheet("""
            QPushButton {
                background-color: #FF6B35;
                color: white;
                font-size: 20px;
                font-weight: bold;
                padding: 15px;
                border-radius: 10px;
                border: none;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #FF5722;
                transform: scale(1.02);
            }
            QPushButton:pressed {
                background-color: #E64A19;
                transform: scale(0.98);
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
        """)
        self.add_button.clicked.connect(self.add_to_cart_clicked.emit)
        self.add_button.setEnabled(False)
        buttons_layout.addWidget(self.add_button, 2)  # Give more space
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
    
    def add_detected_product(self, product: Product):
        """Add detected product to list"""
        # Check if product is already in the list
        for existing_product in self.detected_products:
            if existing_product.id == product.id:
                logger.info(f"Product {product.name} already in detected list")
                return
        
        self.detected_products.append(product)
        
        # Create item widget
        index = len(self.detected_products) - 1
        item_widget = DetectedItemWidget(product, index)
        item_widget.delete_clicked.connect(self.on_delete_item)
        self.detected_layout.addWidget(item_widget)
        
        self.add_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        logger.info(f"Added to detected list: {product.name}")
    
    def on_delete_item(self, index):
        """Handle item deletion"""
        if 0 <= index < len(self.detected_products):
            removed_product = self.detected_products.pop(index)
            logger.info(f"Removed from detected list: {removed_product.name}")
            
            # Rebuild the display
            self.refresh_display()
    
    def refresh_display(self):
        """Refresh the detected items display"""
        # Clear existing widgets
        while self.detected_layout.count():
            child = self.detected_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # If no products, show empty state
        if not self.detected_products:
            empty_label = QLabel("No items detected Click 📷 SCAN to detect products")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("""
                QLabel {
                    color: #666666;
                    font-size: 14px;
                    padding: 20px;
                    background-color: transparent;
                }
            """)
            self.detected_layout.addWidget(empty_label)
        else:
            # Re-add all items
            for index, product in enumerate(self.detected_products):
                item_widget = DetectedItemWidget(product, index)
                item_widget.delete_clicked.connect(self.on_delete_item)
                self.detected_layout.addWidget(item_widget)
        
        # Add stretch at the end
        self.detected_layout.addStretch()
        
        # Update button states
        self.add_button.setEnabled(len(self.detected_products) > 0)
        self.clear_button.setEnabled(len(self.detected_products) > 0)
    
    def clear_detected(self):
        """Clear detected products"""
        self.detected_products.clear()
        self.refresh_display()
        logger.info("Cleared detected products")


class StatusWidget(QWidget):
    """Status bar widget showing connection status"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.api_connected = False
        self.last_send_time = None
    
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        
        self.setStyleSheet("""
            QWidget {
                background-color: #333333;
                border-top: 2px solid #444444;
            }
        """)
        
        # Connection status
        self.connection_label = QLabel("● API: Checking...")
        self.connection_label.setStyleSheet("""
            QLabel {
                color: #999999;
                font-size: 12px;
                background-color: transparent;
            }
        """)
        layout.addWidget(self.connection_label)
        
        layout.addStretch()
        
        # Last action
        self.action_label = QLabel("Ready")
        self.action_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 12px;
                background-color: transparent;
            }
        """)
        layout.addWidget(self.action_label)
        
        layout.addStretch()
        
        # Time
        self.time_label = QLabel("")
        self.time_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 12px;
                background-color: transparent;
            }
        """)
        layout.addWidget(self.time_label)
        
        self.setLayout(layout)
        
        # Update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
    
    def update_time(self):
        current_time = datetime.now().strftime("%H:%M:%S")
        self.time_label.setText(current_time)
    
    def set_api_status(self, connected):
        self.api_connected = connected
        if connected:
            self.connection_label.setText("● API: Connected")
            self.connection_label.setStyleSheet("""
                QLabel {
                    color: #4CAF50;
                    font-size: 12px;
                    background-color: transparent;
                }
            """)
        else:
            self.connection_label.setText("● API: Disconnected")
            self.connection_label.setStyleSheet("""
                QLabel {
                    color: #F44336;
                    font-size: 12px;
                    background-color: transparent;
                }
            """)
    
    def set_action(self, action):
        self.action_label.setText(action)
        self.last_send_time = datetime.now()


class DarkMessageBox(QMessageBox):
    """Custom dark-themed message box"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet("""
            QMessageBox {
                background-color: #3A3A3A;
                color: #FFFFFF;
            }
            QMessageBox QLabel {
                color: #FFFFFF;
                font-size: 16px;
            }
            QMessageBox QPushButton {
                background-color: #FF6B35;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-size: 14px;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #FF5722;
            }
            QMessageBox QPushButton:pressed {
                background-color: #E64A19;
            }
        """)


class MainWindow(QMainWindow):
    """Main application window - Enhanced for hybrid system"""
    
    def __init__(self):
        super().__init__()
        
        # Load settings
        with open('config/settings.json', 'r') as f:
            self.settings = json.load(f)
        
        # API Configuration
        self.api_base_url = "http://localhost:8000"
        self.api_timeout = 5  # seconds
        self.batch_send = True  # Send all items at once
        
        # Initialize components
        self.db_manager = DatabaseManager()
        self.cart = ShoppingCart()  # Local preview cart
        
        # Initialize detection system
        model_paths = {
            'chips': 'trained_models/chips_model.pt',
            'drinks': 'trained_models/drinks_model.pt'
        }
        self.detector = YOLODetector(model_paths, conf_threshold=self.settings['detection']['confidence_threshold'])
        
        # Initialize camera
        if self.settings['camera']['use_ip_camera']:
            camera_source = self.settings['camera']['ip_camera_url']
        else:
            camera_source = self.settings['camera']['default_source']
        
        self.video_stream = VideoStream(camera_source)
        
        # Setup UI
        self.setup_ui()
        
        # Connect signals
        self.connect_signals()
        
        # Apply settings
        self.apply_settings()
        
        # Check API connection
        self.check_api_connection()
    
    def setup_ui(self):
        """Setup main window UI"""
        self.setWindowTitle("Smart Checkout Scanner - Hybrid Mode")
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = QWidget()
        header.setStyleSheet("""
            QWidget {
                background-color: #1F1F1F;
                border-bottom: 2px solid #FF6B35;
            }
        """)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(20, 10, 20, 10)
        
        title_label = QLabel("🛒 SMART CHECKOUT SCANNER")
        title_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-size: 24px;
                font-weight: bold;
                background-color: transparent;
            }
        """)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Web button
        self.web_button = QPushButton("🌐 Open Web Interface")
        self.web_button.setStyleSheet("""
            QPushButton {
                background-color: #FF6B35;
                color: white;
                font-size: 14px;
                padding: 8px 16px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #FF5722;
            }
        """)
        self.web_button.clicked.connect(self.open_web_interface)
        header_layout.addWidget(self.web_button)
        
        header.setLayout(header_layout)
        main_layout.addWidget(header)
        
        # Content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        # Left side - Camera
        self.camera_widget = CameraWidget(self.detector, self.video_stream)
        content_layout.addWidget(self.camera_widget, 2)
        
        # Center - Scanner controls
        self.scanner_widget = ScannerWidget()
        self.scanner_widget.setMaximumWidth(400)
        content_layout.addWidget(self.scanner_widget, 1)
        
        # Right side - Cart preview
        self.cart_widget = CartWidget(self.cart)
        self.cart_widget.setMaximumWidth(350)
        content_layout.addWidget(self.cart_widget, 1)
        
        content_widget = QWidget()
        content_widget.setLayout(content_layout)
        main_layout.addWidget(content_widget, 1)
        
        # Status bar
        self.status_widget = StatusWidget()
        main_layout.addWidget(self.status_widget)
        
        central_widget.setLayout(main_layout)
    
    def connect_signals(self):
        """Connect widget signals"""
        # Camera detection
        self.camera_widget.products_detected.connect(self.on_products_detected)
        
        # Scanner controls
        self.scanner_widget.scan_clicked.connect(self.on_scan_clicked)
        self.scanner_widget.add_to_cart_clicked.connect(self.on_add_to_web_cart)
        
        # Cart (local preview only)
        self.cart_widget.checkout_clicked.connect(self.on_checkout)
    
    def apply_settings(self):
        """Apply settings to window"""
        # Window size - fixed at 1240x720
        self.setFixedSize(1240, 720)
        
        # Style
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {self.settings['ui']['colors']['background']};
            }}
            QWidget {{
                color: {self.settings['ui']['colors']['text']};
                font-size: {self.settings['ui']['font_size']['medium']}px;
            }}
        """)
    
    def check_api_connection(self):
     """Check if API is accessible"""
    try:
        response = requests.get(f"{self.api_base_url}/api/system-status", timeout=2)
        if response.status_code == 200:
            self.status_widget.set_api_status(True)
            logger.info("API connection successful")
        else:
            self.status_widget.set_api_status(False)
            logger.warning("API returned non-200 status")
    except:
        self.status_widget.set_api_status(False)
        logger.warning("Cannot connect to API")
        
        # Show warning
        msg = DarkMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("API Connection")
        # FIX: This line was missing the closing quote and parenthesis
        msg.setText("Cannot connect to web server!\n\n"
           "Please ensure the web server is running on port 8000")
        msg.exec_()
    
    def on_scan_clicked(self):
        """Handle scan button click - take a snapshot"""
        logger.info("Taking snapshot...")
        self.status_widget.set_action("Scanning...")
        
        # Clear previous detections
        self.scanner_widget.clear_detected()
        
        # Capture and detect
        detections = self.camera_widget.capture_and_detect()
    
    def on_products_detected(self, detections):
        """Handle detected products from snapshot"""
        for detection in detections:
            logger.info(f"Product detected: {detection['class_name']}")
            
            # Look up product in database
            product_data = self.db_manager.get_product_by_yolo_class(detection['class_name'])
            
            if product_data:
                logger.info(f"Found product in database: {product_data['name']}")
                # Create Product object
                product = Product(
                    id=product_data['id'],
                    name=product_data['name'],
                    price=product_data['price'],
                    category=product_data['category'],
                    barcode=product_data.get('barcode'),
                    stock=product_data.get('stock', 0),
                    image=product_data.get('image'),
                    description=product_data.get('description'),
                    weight=product_data.get('weight'),
                    volume=product_data.get('volume'),
                    yolo_class_name=product_data.get('yolo_class_name')
                )
                
                # Add to scanner widget
                self.scanner_widget.add_detected_product(product)
                
                # Add to local preview cart
                self.cart.add_product(product)
                self.cart_widget.update_cart_display()
            else:
                logger.warning(f"Product not found in database: {detection['class_name']}")
        
        if len(detections) > 0:
            self.status_widget.set_action(f"Detected {len(detections)} items")
        else:
            self.status_widget.set_action("No products detected")
    
    def on_add_to_web_cart(self):
        """Send detected products to web cart via API"""
        if not self.scanner_widget.detected_products:
            return
        
        logger.info(f"Sending {len(self.scanner_widget.detected_products)} products to web cart")
        self.status_widget.set_action("Sending to web cart...")
        
        if self.batch_send:
            # Send all items at once
            self.send_batch_to_api()
        else:
            # Send items one by one
            self.send_individual_to_api()
    
    def send_batch_to_api(self):
        """Send all items in a single batch request"""
        items = []
        for product in self.scanner_widget.detected_products:
            items.append({
                "product_id": product.id,
                "quantity": 1
            })
        
        try:
            response = requests.post(
                f"{self.api_base_url}/api/add-batch-to-cart",
                json={"items": items},
                timeout=self.api_timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                success_count = result.get('items_added', 0)
                errors = result.get('errors', [])
                
                if success_count > 0:
                    self.show_success_message(success_count, errors)
                    self.scanner_widget.clear_detected()
                    self.cart.clear()
                    self.cart_widget.update_cart_display()
                    self.status_widget.set_action(f"Sent {success_count} items")
                else:
                    self.show_error_message(errors)
                    self.status_widget.set_action("Failed to send items")
            else:
                self.show_connection_error()
                self.status_widget.set_action("API error")
                
        except requests.exceptions.ConnectionError:
            self.show_connection_error()
            self.status_widget.set_api_status(False)
            self.status_widget.set_action("Connection failed")
        except Exception as e:
            logger.error(f"Error sending batch: {e}")
            self.show_error_message([str(e)])
            self.status_widget.set_action("Error")
    
    def send_individual_to_api(self):
        """Send items one by one (fallback method)"""
        success_count = 0
        error_messages = []
        
        for product in self.scanner_widget.detected_products:
            try:
                response = requests.post(
                    f"{self.api_base_url}/api/add-to-cart",
                    json={"product_id": product.id},
                    timeout=self.api_timeout
                )
                
                if response.status_code == 200:
                    logger.info(f"✓ Added {product.name} to web cart")
                    success_count += 1
                else:
                    error_data = response.json()
                    error_msg = error_data.get('error', 'Unknown error')
                    error_messages.append(f"{product.name}: {error_msg}")
                    logger.warning(f"Failed to add {product.name}: {error_msg}")
                    
            except requests.exceptions.ConnectionError:
                error_messages.append("Cannot connect to web server")
                self.status_widget.set_api_status(False)
                break
            except Exception as e:
                error_messages.append(f"{product.name}: {str(e)}")
        
        if success_count > 0:
            self.show_success_message(success_count, error_messages)
            self.scanner_widget.clear_detected()
            self.cart.clear()
            self.cart_widget.update_cart_display()
            self.status_widget.set_action(f"Sent {success_count} items")
        else:
            self.show_error_message(error_messages)
            self.status_widget.set_action("Failed to send")
    
    def show_success_message(self, count, errors):
        """Show success message with option to open web"""
        msg = DarkMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Success")
        
        message = f"✅ Successfully sent {count} item(s) to web cart!"
        
        if errors:
            message += f"\n\n⚠️ Some items failed:\n" + "\n".join(errors[:3])
        
        message += "\n\nWould you like to open the web interface?"
        
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        
        if msg.exec_() == QMessageBox.Yes:
            self.open_web_interface()
    
    def show_error_message(self, errors):
        """Show error message"""
        msg = DarkMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Error")
        error_text = "\n".join(errors[:5])
        msg.setText(f"Failed to send items:\n\n{error_text}")
        msg.exec_()
    
    def show_connection_error(self):
        """Show connection error message"""
        msg = DarkMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Connection Error")
        msg.setText("Cannot connect to web server!\n\n"
                    "Please ensure the web server is running on port 8000")
        msg.exec_() 
    
    def show_connection_error(self):
        """Show connection error message"""
        msg = DarkMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Connection Error")
        msg.setText("Cannot connect to web server!\n\n"
                    "Please ensure the web server is running on port 8000")
        msg.exec_()
    
    def open_web_interface(self):
        """Open web interface in browser"""
        import webbrowser
        webbrowser.open(f"{self.api_base_url}/cart")
        self.status_widget.set_action("Opened web interface")
    
    def on_checkout(self):
        """Handle checkout - not used in hybrid mode"""
        msg = DarkMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Hybrid Mode")
        msg.setText("Checkout is handled through the web interface.\n\n"
           "Please send items to web cart first.")
        msg.exec_()
    
    def closeEvent(self, event):
        """Clean up on close"""
        self.video_stream.stop()
        event.accept()

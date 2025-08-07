#!/usr/bin/env python3
"""
COMPLETE HYBRID SMART CHECKOUT SYSTEM SETUP
============================================
This script will create and configure the entire hybrid system with all features.
Run this script to set up everything automatically.
"""

import os
import sys
import json
import shutil
from pathlib import Path

# ============================================================================
# PART 1: COMPLETE WEB SYSTEM FILES
# ============================================================================

WEB_FILES = {
    # Enhanced main.py with all features
    "main.py": '''from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import json
import asyncio
from datetime import datetime, timedelta
import os
from pathlib import Path
import base64
import cv2
import numpy as np
import qrcode
from io import BytesIO
import uuid
from typing import List, Dict, Optional
import logging

from services.detection_service import DetectionService
from services.json_db import JsonDatabase

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
db = JsonDatabase()
detection_service = DetectionService(db)

# WebSocket connections manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# Global cart management with session support
class CartManager:
    def __init__(self):
        self.carts = {}  # session_id -> cart
        self.default_session = "default"
        
    def get_cart(self, session_id: str = None) -> dict:
        if not session_id:
            session_id = self.default_session
        
        if session_id not in self.carts:
            self.carts[session_id] = {
                "items": [],
                "last_updated": None,
                "created_at": datetime.now().isoformat()
            }
        
        return self.carts[session_id]
    
    def add_item(self, product: dict, session_id: str = None) -> dict:
        cart = self.get_cart(session_id)
        
        # Add with timestamp and unique ID
        item = {
            "id": str(uuid.uuid4()),
            "product_id": product["id"],
            "product_name": product["name"],
            "price": product["price"],
            "category": product["category"],
            "timestamp": datetime.now().isoformat(),
            "scanner_source": "pyqt"  # Track source
        }
        
        cart["items"].append(item)
        cart["last_updated"] = datetime.now().isoformat()
        
        return item
    
    def remove_item(self, product_id: str, session_id: str = None) -> bool:
        cart = self.get_cart(session_id)
        
        for i, item in enumerate(cart["items"]):
            if item["product_id"] == product_id:
                cart["items"].pop(i)
                cart["last_updated"] = datetime.now().isoformat()
                return True
        
        return False
    
    def clear_cart(self, session_id: str = None):
        cart = self.get_cart(session_id)
        cart["items"] = []
        cart["last_updated"] = datetime.now().isoformat()
    
    def get_summary(self, session_id: str = None) -> dict:
        cart = self.get_cart(session_id)
        
        # Group by product_id
        summary = {}
        for item in cart["items"]:
            pid = item["product_id"]
            if pid in summary:
                summary[pid]["quantity"] += 1
            else:
                summary[pid] = {
                    "product_id": pid,
                    "product_name": item["product_name"],
                    "price": item["price"],
                    "quantity": 1
                }
        
        return {
            "items": list(summary.values()),
            "total_items": len(cart["items"]),
            "unique_items": len(summary),
            "last_updated": cart["last_updated"],
            "created_at": cart.get("created_at")
        }
    
    def cleanup_old_carts(self, max_age_hours: int = 24):
        """Remove carts older than max_age_hours"""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        for session_id in list(self.carts.keys()):
            cart = self.carts[session_id]
            if cart.get("created_at"):
                created = datetime.fromisoformat(cart["created_at"])
                if created < cutoff and len(cart["items"]) == 0:
                    del self.carts[session_id]
                    logger.info(f"Cleaned up old cart: {session_id}")

cart_manager = CartManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await detection_service.initialize()
    logger.info("Detection service initialized")
    
    # Periodic cleanup task
    async def cleanup_task():
        while True:
            await asyncio.sleep(3600)  # Every hour
            cart_manager.cleanup_old_carts()
    
    asyncio.create_task(cleanup_task())
    
    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(title="Smart Checkout System", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# CART MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/api/add-to-cart")
async def add_to_cart(item_data: dict):
    """Add scanned item from PyQt scanner to cart"""
    try:
        product_id = item_data.get("product_id")
        session_id = item_data.get("session_id", None)
        quantity = item_data.get("quantity", 1)
        
        # Validate product exists
        product = db.get_product(product_id)
        if not product:
            return JSONResponse(
                status_code=404, 
                content={"error": f"Product {product_id} not found"}
            )
        
        # Check stock
        if product["stock"] < quantity:
            return JSONResponse(
                status_code=400,
                content={
                    "error": f"Insufficient stock for {product['name']}",
                    "available": product["stock"],
                    "requested": quantity
                }
            )
        
        # Add to cart (support multiple quantities)
        added_items = []
        for _ in range(quantity):
            item = cart_manager.add_item(product, session_id)
            added_items.append(item)
        
        # Get updated summary
        summary = cart_manager.get_summary(session_id)
        
        # Broadcast update
        await manager.broadcast({
            "type": "cart_updated",
            "session_id": session_id or "default",
            "product_name": product["name"],
            "action": "added",
            "cart_size": summary["total_items"]
        })
        
        logger.info(f"Added {quantity}x {product['name']} to cart")
        
        return {
            "success": True,
            "message": f"Added {quantity}x {product['name']} to cart",
            "cart_summary": summary,
            "items_added": added_items
        }
        
    except Exception as e:
        logger.error(f"Error adding to cart: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.post("/api/add-batch-to-cart")
async def add_batch_to_cart(batch_data: dict):
    """Add multiple items at once from PyQt scanner"""
    try:
        items = batch_data.get("items", [])
        session_id = batch_data.get("session_id", None)
        
        results = []
        errors = []
        
        for item in items:
            product_id = item.get("product_id")
            quantity = item.get("quantity", 1)
            
            product = db.get_product(product_id)
            if not product:
                errors.append(f"Product {product_id} not found")
                continue
            
            if product["stock"] < quantity:
                errors.append(f"Insufficient stock for {product['name']}")
                continue
            
            for _ in range(quantity):
                cart_item = cart_manager.add_item(product, session_id)
                results.append(cart_item)
        
        summary = cart_manager.get_summary(session_id)
        
        # Broadcast update
        await manager.broadcast({
            "type": "batch_added",
            "session_id": session_id or "default",
            "items_count": len(results),
            "cart_size": summary["total_items"]
        })
        
        return {
            "success": len(results) > 0,
            "items_added": len(results),
            "errors": errors,
            "cart_summary": summary
        }
        
    except Exception as e:
        logger.error(f"Error in batch add: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/cart")
async def get_cart(session_id: str = None):
    """Get current cart contents"""
    summary = cart_manager.get_summary(session_id)
    return summary

@app.delete("/api/cart")
async def clear_cart(session_id: str = None):
    """Clear the cart"""
    cart_manager.clear_cart(session_id)
    
    await manager.broadcast({
        "type": "cart_cleared",
        "session_id": session_id or "default"
    })
    
    logger.info(f"Cart cleared for session: {session_id or 'default'}")
    
    return {"success": True, "message": "Cart cleared"}

@app.delete("/api/cart/{product_id}")
async def remove_from_cart(product_id: str, session_id: str = None):
    """Remove one instance of a product from cart"""
    if cart_manager.remove_item(product_id, session_id):
        summary = cart_manager.get_summary(session_id)
        
        await manager.broadcast({
            "type": "item_removed",
            "session_id": session_id or "default",
            "product_id": product_id,
            "cart_size": summary["total_items"]
        })
        
        return {
            "success": True,
            "message": f"Removed item from cart",
            "cart_summary": summary
        }
    
    return JSONResponse(
        status_code=404,
        content={"error": "Item not found in cart"}
    )

@app.post("/api/checkout-cart")
async def checkout_cart(checkout_data: dict = None):
    """Create payment from current cart"""
    session_id = checkout_data.get("session_id") if checkout_data else None
    summary = cart_manager.get_summary(session_id)
    
    if summary["total_items"] == 0:
        return JSONResponse(
            status_code=400,
            content={"error": "Cart is empty"}
        )
    
    # Prepare items for payment
    cart_data = {
        "items": [
            {"product_id": item["product_id"], "quantity": item["quantity"]}
            for item in summary["items"]
        ]
    }
    
    # Generate payment
    payment_id = str(uuid.uuid4())
    subtotal = sum(item["price"] * item["quantity"] for item in summary["items"])
    
    settings = db.get_settings()
    tax_rate = settings.get("tax_rate", 0.07)
    tax = subtotal * tax_rate
    total = subtotal + tax
    
    # Generate QR code
    qr_data = f"PAYMENT|{total:.2f}|{payment_id}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    pending_payment = {
        "payment_id": payment_id,
        "timestamp": datetime.now().isoformat(),
        "items": [
            {
                "product_id": item["product_id"],
                "product_name": item["product_name"],
                "quantity": item["quantity"],
                "price": item["price"],
                "total": item["price"] * item["quantity"]
            }
            for item in summary["items"]
        ],
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "status": "pending",
        "qr_code": f"data:image/png;base64,{qr_base64}",
        "session_id": session_id or "default"
    }
    
    db.add_pending_payment(payment_id, pending_payment)
    
    # Clear cart after creating payment
    cart_manager.clear_cart(session_id)
    
    await manager.broadcast({
        "type": "payment_created",
        "session_id": session_id or "default",
        "payment_id": payment_id
    })
    
    logger.info(f"Payment created: {payment_id} for ฿{total:.2f}")
    
    return pending_payment

# ============================================================================
# EXISTING ENDPOINTS (Keep all your existing endpoints)
# ============================================================================

@app.get("/api/products")
async def get_products():
    return db.get_products()

@app.post("/api/restock/{product_id}")
async def restock_product(product_id: str, quantity: int):
    success = db.update_stock(product_id, quantity, operation="add")
    if success:
        await manager.broadcast({"type": "stock_update", "product_id": product_id})
        return {"message": "Product restocked successfully"}
    return JSONResponse(status_code=400, content={"error": "Failed to restock"})

@app.post("/api/confirm-payment/{payment_id}")
async def confirm_payment(payment_id: str):
    pending_payment = db.get_pending_payment(payment_id)
    
    if not pending_payment:
        return JSONResponse(status_code=404, content={"error": "Payment not found"})
    
    if pending_payment["status"] != "pending":
        return JSONResponse(status_code=400, content={"error": "Payment already processed"})
    
    sale = db.process_pending_payment(payment_id)
    
    if sale:
        await manager.broadcast({"type": "sale_completed", "sale": sale})
        logger.info(f"Payment confirmed: {payment_id}")
        return sale
    
    return JSONResponse(status_code=400, content={"error": "Failed to process payment"})

@app.get("/api/sales")
async def get_sales(limit: int = 50):
    return db.get_sales(limit)

@app.get("/api/analytics")
async def get_analytics():
    return db.get_analytics()

@app.get("/api/theme")
async def get_theme():
    return {"theme": db.get_theme()}

@app.post("/api/theme")
async def set_theme(theme_data: dict):
    theme = theme_data.get("theme", "light")
    if theme in ["light", "dark"]:
        db.set_theme(theme)
        await manager.broadcast({"type": "theme_changed", "theme": theme})
        return {"theme": theme}
    return JSONResponse(status_code=400, content={"error": "Invalid theme"})

@app.get("/api/system-status")
async def system_status():
    """Get system status for monitoring"""
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "active_connections": len(manager.active_connections),
        "active_carts": len(cart_manager.carts),
        "detection_service": detection_service.initialized
    }

@app.websocket("/ws/detection")
async def websocket_detection(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "frame":
                frame_data = data.get("frame")
                if frame_data:
                    img_data = base64.b64decode(frame_data.split(',')[1])
                    nparr = np.frombuffer(img_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    detections = await detection_service.detect_frame(frame)
                    
                    await websocket.send_json({
                        "type": "detections",
                        "data": detections
                    })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Static file serving
@app.get("/")
async def root():
    return FileResponse("static/inventory.html")

@app.get("/cart")
async def cart_page():
    return FileResponse("static/cart.html")

@app.get("/admin")
async def admin_page():
    return FileResponse("static/admin.html")

@app.get("/monitor")
async def monitor_page():
    return FileResponse("static/monitor.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/models", StaticFiles(directory="models"), name="models")

if __name__ == "__main__":
    print("\\n" + "="*60)
    print("🚀 HYBRID SMART CHECKOUT SYSTEM v3.0")
    print("="*60)
    print("\\n📍 Access Points:")
    print("   Inventory: http://localhost:8000")
    print("   Cart:      http://localhost:8000/cart")
    print("   Analytics: http://localhost:8000/admin")
    print("   Monitor:   http://localhost:8000/monitor")
    print("\\n🔧 API Endpoints:")
    print("   POST /api/add-to-cart     - Add single item")
    print("   POST /api/add-batch-to-cart - Add multiple items")
    print("   GET  /api/cart            - Get cart contents")
    print("   POST /api/checkout-cart   - Create payment")
    print("="*60 + "\\n")
    
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
''',

    # Enhanced cart.html with better UX
    "static/cart.html": '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Shopping Cart - Smart Checkout</title>
    <link rel="stylesheet" href="/static/css/style.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        .pulse-animation {
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }
        
        .slide-in {
            animation: slideIn 0.3s ease-out;
        }
        
        @keyframes slideIn {
            from { 
                opacity: 0;
                transform: translateX(-20px);
            }
            to { 
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        .scanner-status {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: var(--bg-primary);
            border: 2px solid var(--border);
            border-radius: 12px;
            padding: 1rem;
            box-shadow: var(--shadow-md);
            z-index: 100;
            min-width: 250px;
        }
        
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 8px;
            animation: blink 1s infinite;
        }
        
        .status-indicator.connected {
            background: var(--success);
        }
        
        .status-indicator.disconnected {
            background: var(--danger);
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .cart-item-enter {
            animation: itemEnter 0.4s ease-out;
        }
        
        @keyframes itemEnter {
            from {
                opacity: 0;
                transform: translateY(-10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--success);
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            box-shadow: var(--shadow-md);
            display: none;
            z-index: 1000;
            animation: notificationSlide 0.3s ease-out;
        }
        
        @keyframes notificationSlide {
            from {
                transform: translateX(400px);
            }
            to {
                transform: translateX(0);
            }
        }
    </style>
</head>
<body>
    <div class="app-container">
        <header class="app-header">
            <div class="header-content">
                <div>
                    <h1>
                        <i class="fas fa-shopping-cart"></i> Shopping Cart
                    </h1>
                    <span style="font-size: 0.875rem; color: var(--text-secondary);">
                        Items from PyQt Scanner • Real-time sync enabled
                    </span>
                </div>
                <nav class="header-nav" style="display: flex; gap: 1rem;">
                    <button class="nav-btn" onclick="window.location.href='/'">
                        <i class="fas fa-boxes"></i> Inventory
                    </button>
                    <button class="nav-btn" onclick="window.location.href='/admin'">
                        <i class="fas fa-chart-line"></i> Analytics
                    </button>
                    <button class="theme-toggle" onclick="themeManager.toggle()">
                        <div class="theme-toggle-slider">☀️</div>
                    </button>
                </nav>
            </div>
        </header>

        <main class="main-content">
            <!-- Quick Stats Bar -->
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem;">
                <div class="stat-card fade-in" style="animation-delay: 0s;">
                    <div style="display: flex; align-items: center; gap: 1rem;">
                        <div style="font-size: 2rem;">📦</div>
                        <div>
                            <div style="font-size: 1.5rem; font-weight: bold;" id="statItems">0</div>
                            <div style="font-size: 0.75rem; color: var(--text-secondary);">Total Items</div>
                        </div>
                    </div>
                </div>
                
                <div class="stat-card fade-in" style="animation-delay: 0.1s;">
                    <div style="display: flex; align-items: center; gap: 1rem;">
                        <div style="font-size: 2rem;">🛍️</div>
                        <div>
                            <div style="font-size: 1.5rem; font-weight: bold;" id="statUnique">0</div>
                            <div style="font-size: 0.75rem; color: var(--text-secondary);">Unique Products</div>
                        </div>
                    </div>
                </div>
                
                <div class="stat-card fade-in" style="animation-delay: 0.2s;">
                    <div style="display: flex; align-items: center; gap: 1rem;">
                        <div style="font-size: 2rem;">💰</div>
                        <div>
                            <div style="font-size: 1.5rem; font-weight: bold;" id="statSubtotal">฿0</div>
                            <div style="font-size: 0.75rem; color: var(--text-secondary);">Subtotal</div>
                        </div>
                    </div>
                </div>
                
                <div class="stat-card fade-in" style="animation-delay: 0.3s;">
                    <div style="display: flex; align-items: center; gap: 1rem;">
                        <div style="font-size: 2rem;">⏱️</div>
                        <div>
                            <div style="font-size: 1.5rem; font-weight: bold;" id="statTime">--:--</div>
                            <div style="font-size: 0.75rem; color: var(--text-secondary);">Last Update</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Cart Actions Bar -->
            <div style="background: var(--bg-primary); border: 1px solid var(--border); border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1.5rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h2 style="margin-bottom: 0.5rem;">
                            <i class="fas fa-barcode"></i> Scanner Integration
                        </h2>
                        <p style="color: var(--text-secondary); font-size: 0.875rem;">
                            <span class="status-indicator connected"></span>
                            PyQt Scanner is ready • Items appear here automatically
                        </p>
                    </div>
                    <div style="display: flex; gap: 1rem;">
                        <button class="btn btn-secondary" onclick="cartManager.refreshCart()">
                            <i class="fas fa-sync"></i> Refresh
                        </button>
                        <button id="clearCartBtn" class="btn btn-secondary" onclick="clearCart()">
                            <i class="fas fa-trash"></i> Clear Cart
                        </button>
                    </div>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem;">
                <!-- Cart Items -->
                <div style="background: var(--bg-primary); border: 1px solid var(--border); border-radius: 0.75rem; padding: 1.5rem;">
                    <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 1rem;">
                        <h3>
                            <i class="fas fa-list"></i> Cart Items
                            <span id="itemCount" style="background: var(--primary); color: white; padding: 0.25rem 0.5rem; border-radius: 1rem; font-size: 0.75rem; margin-left: 0.5rem;">0</span>
                        </h3>
                    </div>
                    
                    <div id="cartItems" style="min-height: 400px; max-height: 600px; overflow-y: auto;">
                        <div class="empty-cart" style="text-align: center; padding: 4rem; color: var(--text-secondary);">
                            <i class="fas fa-shopping-cart" style="font-size: 4rem; margin-bottom: 1rem; opacity: 0.3;"></i>
                            <h3>Your cart is empty</h3>
                            <p style="font-size: 0.875rem; margin-top: 0.5rem;">
                                Use the PyQt scanner to add products
                            </p>
                            <div style="margin-top: 2rem; padding: 1rem; background: var(--bg-secondary); border-radius: 0.5rem; text-align: left;">
                                <h4 style="margin-bottom: 0.5rem;">📱 How to scan:</h4>
                                <ol style="font-size: 0.875rem; margin-left: 1.5rem;">
                                    <li>Open PyQt Scanner application</li>
                                    <li>Click "📷 Scan!" button</li>
                                    <li>Point at products</li>
                                    <li>Click "🌐 Send to Web Cart"</li>
                                    <li>Items will appear here instantly!</li>
                                </ol>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Cart Summary & Payment -->
                <div>
                    <div style="background: var(--bg-primary); border: 1px solid var(--border); border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1rem;">
                        <h3 style="margin-bottom: 1rem;">
                            <i class="fas fa-calculator"></i> Summary
                        </h3>
                        
                        <div style="margin-bottom: 1rem;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem; font-size: 0.875rem;">
                                <span>Items:</span>
                                <span id="summaryItems">0</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                                <span>Subtotal:</span>
                                <span id="subtotal">฿0.00</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem; color: var(--text-secondary);">
                                <span>Tax (7%):</span>
                                <span id="tax">฿0.00</span>
                            </div>
                            <div style="border-top: 2px solid var(--border); padding-top: 0.5rem; margin-top: 0.5rem;">
                                <div style="display: flex; justify-content: space-between; font-size: 1.5rem; font-weight: bold;">
                                    <span>Total:</span>
                                    <span id="total" style="color: var(--primary);">฿0.00</span>
                                </div>
                            </div>
                        </div>

                        <button id="checkoutBtn" class="btn btn-primary pulse-animation" style="width: 100%; padding: 1rem; font-size: 1.125rem;" onclick="proceedToCheckout()" disabled>
                            <i class="fas fa-qrcode"></i> Generate QR Payment
                        </button>
                    </div>

                    <!-- Payment Methods Info -->
                    <div style="background: var(--bg-primary); border: 1px solid var(--border); border-radius: 0.75rem; padding: 1.5rem;">
                        <h4 style="margin-bottom: 1rem;">
                            <i class="fas fa-credit-card"></i> Payment Methods
                        </h4>
                        <div style="display: grid; gap: 0.5rem; font-size: 0.875rem;">
                            <div style="padding: 0.5rem; background: var(--bg-secondary); border-radius: 0.5rem;">
                                <i class="fas fa-qrcode" style="color: var(--primary);"></i> QR PromptPay
                            </div>
                            <div style="padding: 0.5rem; background: var(--bg-secondary); border-radius: 0.5rem;">
                                <i class="fas fa-university" style="color: var(--primary);"></i> Bank Transfer
                            </div>
                            <div style="padding: 0.5rem; background: var(--bg-secondary); border-radius: 0.5rem;">
                                <i class="fas fa-mobile-alt" style="color: var(--primary);"></i> Mobile Banking
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <!-- Scanner Status Widget -->
    <div class="scanner-status">
        <h4 style="margin-bottom: 0.5rem; font-size: 0.875rem;">
            <i class="fas fa-desktop"></i> PyQt Scanner Status
        </h4>
        <div style="font-size: 0.875rem;">
            <div style="margin-bottom: 0.25rem;">
                <span class="status-indicator connected"></span>
                <span id="scannerStatus">Ready</span>
            </div>
            <div style="color: var(--text-secondary);">
                Last scan: <span id="lastScan">Never</span>
            </div>
        </div>
    </div>

    <!-- Notification Toast -->
    <div id="notification" class="notification">
        <i class="fas fa-check-circle"></i>
        <span id="notificationText">Item added to cart!</span>
    </div>

    <!-- Payment Modal -->
    <div id="qrModal" class="modal">
        <div class="modal-content" style="text-align: center; max-width: 500px;">
            <h2>
                <i class="fas fa-qrcode"></i> Scan to Pay
            </h2>
            
            <div style="background: white; padding: 2rem; border-radius: 1rem; margin: 1.5rem 0;">
                <img id="qrImage" src="" alt="Payment QR Code" style="max-width: 250px;">
            </div>
            
            <div style="background: var(--bg-tertiary); padding: 1rem; border-radius: 0.5rem; margin: 1rem 0;">
                <p style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 0.5rem;">Total Amount</p>
                <div class="payment-amount" id="paymentAmount" style="font-size: 2.5rem; font-weight: bold; color: var(--primary);">฿0.00</div>
            </div>
            
            <div style="display: grid; gap: 0.5rem; text-align: left; margin: 1.5rem 0; padding: 1rem; background: var(--bg-secondary); border-radius: 0.5rem;">
                <p style="font-size: 0.875rem;">
                    <i class="fas fa-mobile-alt" style="color: var(--primary);"></i>
                    Open your banking app
                </p>
                <p style="font-size: 0.875rem;">
                    <i class="fas fa-camera" style="color: var(--primary);"></i>
                    Scan this QR code
                </p>
                <p style="font-size: 0.875rem;">
                    <i class="fas fa-check" style="color: var(--primary);"></i>
                    Confirm payment in app
                </p>
                <p style="font-size: 0.875rem;">
                    <i class="fas fa-receipt" style="color: var(--primary);"></i>
                    Click "Payment Complete" below
                </p>
            </div>
            
            <div style="display: flex; gap: 1rem; justify-content: center;">
                <button class="btn btn-secondary" onclick="cancelPayment()" style="min-width: 120px;">
                    <i class="fas fa-times"></i> Cancel
                </button>
                <button class="btn btn-primary" onclick="confirmPaymentComplete()" style="min-width: 150px;">
                    <i class="fas fa-check"></i> Payment Complete
                </button>
            </div>
        </div>
    </div>

    <!-- Success Modal -->
    <div id="successModal" class="modal">
        <div class="modal-content" style="text-align: center;">
            <div style="font-size: 5rem; color: var(--success); margin-bottom: 1rem;">
                <i class="fas fa-check-circle"></i>
            </div>
            <h2 style="margin-bottom: 1rem;">Payment Successful!</h2>
            <p id="receiptNumber" style="color: var(--text-secondary); margin: 1rem 0; font-size: 1.125rem;"></p>
            
            <div style="background: var(--bg-secondary); padding: 1rem; border-radius: 0.5rem; margin: 1.5rem 0;">
                <p style="font-size: 0.875rem; color: var(--text-secondary);">
                    <i class="fas fa-info-circle"></i> Stock has been automatically updated
                </p>
            </div>
            
            <button class="btn btn-primary" onclick="window.location.reload()" style="min-width: 200px; padding: 1rem;">
                <i class="fas fa-shopping-cart"></i> Start New Cart
            </button>
        </div>
    </div>

    <script src="/static/js/theme.js"></script>
    <script src="/static/js/cart.js"></script>
</body>
</html>''',

    # Enhanced cart.js with real-time features
    "static/js/cart.js": '''// Enhanced Cart Management System
class CartManager {
    constructor() {
        this.cart = [];
        this.ws = null;
        this.currentPaymentId = null;
        this.lastUpdate = null;
        this.audioEnabled = true;
        this.init();
    }

    async init() {
        await this.loadCart();
        this.connectWebSocket();
        this.setupAudio();
        this.updateClock();
        
        // Auto-refresh every 10 seconds as backup
        setInterval(() => this.loadCart(true), 10000);
        
        // Update clock every second
        setInterval(() => this.updateClock(), 1000);
    }

    setupAudio() {
        // Create audio context for sound feedback
        this.sounds = {
            add: new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBTGH0fPTgjMGHm7A7+OZURE='),
            remove: new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBTGH0fPTgjMGHm7A7+OZURE='),
            success: new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBTGH0fPTgjMGHm7A7+OZURE=')
        };
    }

    playSound(type) {
        if (this.audioEnabled && this.sounds[type]) {
            this.sounds[type].play().catch(e => console.log('Audio play failed:', e));
        }
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${window.location.host}/ws/detection`);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.updateScannerStatus('Connected', true);
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'cart_updated') {
                this.showNotification(`Added ${data.product_name || 'item'} to cart!`, 'success');
                this.playSound('add');
                this.loadCart();
                this.updateLastScan();
            } else if (data.type === 'batch_added') {
                this.showNotification(`Added ${data.items_count} items to cart!`, 'success');
                this.playSound('add');
                this.loadCart();
                this.updateLastScan();
            } else if (data.type === 'cart_cleared') {
                this.showNotification('Cart cleared', 'info');
                this.loadCart();
            } else if (data.type === 'item_removed') {
                this.playSound('remove');
                this.loadCart();
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateScannerStatus('Error', false);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateScannerStatus('Disconnected', false);
            
            // Reconnect after 3 seconds
            setTimeout(() => this.connectWebSocket(), 3000);
        };
    }

    async loadCart(silent = false) {
        try {
            const response = await fetch('/api/cart');
            const data = await response.json();
            
            const prevItemCount = this.cart.length;
            this.cart = data.items || [];
            
            // Animate new items
            if (!silent && this.cart.length > prevItemCount) {
                setTimeout(() => {
                    const items = document.querySelectorAll('#cartItems .cart-item');
                    items.forEach((item, index) => {
                        if (index >= prevItemCount) {
                            item.classList.add('cart-item-enter');
                        }
                    });
                }, 100);
            }
            
            this.lastUpdate = data.last_updated;
            this.updateDisplay();
            this.updateStats(data);
        } catch (error) {
            console.error('Error loading cart:', error);
            this.showNotification('Failed to load cart', 'error');
        }
    }

    updateDisplay() {
        const container = document.getElementById('cartItems');
        
        if (this.cart.length === 0) {
            container.innerHTML = `
                <div class="empty-cart" style="text-align: center; padding: 4rem; color: var(--text-secondary);">
                    <i class="fas fa-shopping-cart" style="font-size: 4rem; margin-bottom: 1rem; opacity: 0.3;"></i>
                    <h3>Your cart is empty</h3>
                    <p style="font-size: 0.875rem; margin-top: 0.5rem;">
                        Use the PyQt scanner to add products
                    </p>
                    <div style="margin-top: 2rem; padding: 1rem; background: var(--bg-secondary); border-radius: 0.5rem; text-align: left;">
                        <h4 style="margin-bottom: 0.5rem;">📱 How to scan:</h4>
                        <ol style="font-size: 0.875rem; margin-left: 1.5rem;">
                            <li>Open PyQt Scanner application</li>
                            <li>Click "📷 Scan!" button</li>
                            <li>Point at products</li>
                            <li>Click "🌐 Send to Web Cart"</li>
                            <li>Items will appear here instantly!</li>
                        </ol>
                    </div>
                </div>
            `;
            document.getElementById('checkoutBtn').disabled = true;
            this.updateSummary(0, 0, 0, 0);
            return;
        }

        // Group items by category for better display
        const categories = {};
        this.cart.forEach(item => {
            const cat = item.category || 'other';
            if (!categories[cat]) {
                categories[cat] = [];
            }
            categories[cat].push(item);
        });

        let html = '';
        Object.keys(categories).forEach(category => {
            const items = categories[category];
            const catIcon = category === 'chips' ? '🍟' : category === 'drinks' ? '🥤' : '📦';
            
            html += `
                <div style="margin-bottom: 1.5rem;">
                    <h4 style="color: var(--text-secondary); font-size: 0.875rem; margin-bottom: 0.5rem;">
                        ${catIcon} ${category.toUpperCase()} (${items.length})
                    </h4>
            `;
            
            items.forEach(item => {
                html += `
                    <div class="cart-item" style="display: flex; justify-content: space-between; align-items: center; padding: 1rem; background: var(--bg-tertiary); border-radius: 0.5rem; margin-bottom: 0.5rem; border: 1px solid var(--border); transition: all 0.2s;">
                        <div style="flex: 1;">
                            <div style="font-weight: 600; margin-bottom: 0.25rem; font-size: 1rem;">
                                ${item.product_name}
                            </div>
                            <div style="color: var(--text-secondary); font-size: 0.875rem;">
                                ฿${item.price.toFixed(2)} × ${item.quantity}
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 1rem;">
                            <div style="text-align: right;">
                                <div style="font-weight: 600; color: var(--primary); font-size: 1.125rem;">
                                    ฿${(item.price * item.quantity).toFixed(2)}
                                </div>
                            </div>
                            <div style="display: flex; gap: 0.5rem;">
                                <button class="btn btn-secondary" style="padding: 0.5rem; font-size: 0.875rem;" onclick="cartManager.removeItem('${item.product_id}')" title="Remove one">
                                    <i class="fas fa-minus"></i>
                                </button>
                                <button class="btn btn-secondary" style="padding: 0.5rem; font-size: 0.875rem;" onclick="cartManager.addMore('${item.product_id}')" title="Add one more">
                                    <i class="fas fa-plus"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
        });

        container.innerHTML = html;
        document.getElementById('checkoutBtn').disabled = false;
        
        // Update item count badge
        document.getElementById('itemCount').textContent = this.cart.reduce((sum, item) => sum + item.quantity, 0);
        
        // Calculate totals
        const itemCount = this.cart.reduce((sum, item) => sum + item.quantity, 0);
        const subtotal = this.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
        const tax = subtotal * 0.07;
        const total = subtotal + tax;
        
        this.updateSummary(itemCount, subtotal, tax, total);
    }

    updateStats(data) {
        // Update quick stats
        const totalItems = data.total_items || 0;
        const uniqueItems = data.unique_items || 0;
        const subtotal = this.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
        
        document.getElementById('statItems').textContent = totalItems;
        document.getElementById('statUnique').textContent = uniqueItems;
        document.getElementById('statSubtotal').textContent = `฿${subtotal.toFixed(0)}`;
        
        // Update time if available
        if (data.last_updated) {
            const date = new Date(data.last_updated);
            const timeStr = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
            document.getElementById('statTime').textContent = timeStr;
        }
    }

    updateSummary(itemCount, subtotal, tax, total) {
        document.getElementById('summaryItems').textContent = itemCount;
        document.getElementById('subtotal').textContent = `฿${subtotal.toFixed(2)}`;
        document.getElementById('tax').textContent = `฿${tax.toFixed(2)}`;
        document.getElementById('total').textContent = `฿${total.toFixed(2)}`;
    }

    async removeItem(productId) {
        try {
            const response = await fetch(`/api/cart/${productId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                this.showNotification('Item removed', 'info');
                await this.loadCart();
            }
        } catch (error) {
            console.error('Error removing item:', error);
            this.showNotification('Failed to remove item', 'error');
        }
    }

    async addMore(productId) {
        try {
            const response = await fetch('/api/add-to-cart', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_id: productId, quantity: 1 })
            });
            
            if (response.ok) {
                this.showNotification('Added one more', 'success');
                this.playSound('add');
                await this.loadCart();
            } else {
                const error = await response.json();
                this.showNotification(error.error || 'Failed to add item', 'error');
            }
        } catch (error) {
            console.error('Error adding item:', error);
            this.showNotification('Failed to add item', 'error');
        }
    }

    async clearCart() {
        if (!confirm('Are you sure you want to clear the entire cart?')) return;
        
        try {
            const response = await fetch('/api/cart', {
                method: 'DELETE'
            });
            
            if (response.ok) {
                this.showNotification('Cart cleared', 'info');
                await this.loadCart();
            }
        } catch (error) {
            console.error('Error clearing cart:', error);
            this.showNotification('Failed to clear cart', 'error');
        }
    }

    async refreshCart() {
        this.showNotification('Refreshing cart...', 'info');
        await this.loadCart();
    }

    async proceedToCheckout() {
        if (this.cart.length === 0) return;
        
        try {
            const response = await fetch('/api/checkout-cart', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (response.ok) {
                const payment = await response.json();
                this.currentPaymentId = payment.payment_id;
                
                document.getElementById('qrImage').src = payment.qr_code;
                document.getElementById('paymentAmount').textContent = `฿${payment.total.toFixed(2)}`;
                document.getElementById('qrModal').style.display = 'block';
                
                this.playSound('success');
            } else {
                const error = await response.json();
                this.showNotification(error.error || 'Failed to create payment', 'error');
            }
        } catch (error) {
            console.error('Checkout error:', error);
            this.showNotification('Error creating payment', 'error');
        }
    }

    async confirmPaymentComplete() {
        if (!this.currentPaymentId) return;
        
        try {
            const response = await fetch(`/api/confirm-payment/${this.currentPaymentId}`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const sale = await response.json();
                document.getElementById('qrModal').style.display = 'none';
                document.getElementById('receiptNumber').textContent = `Receipt: ${sale.id}`;
                document.getElementById('successModal').style.display = 'block';
                
                this.playSound('success');
                
                // Cart will be cleared automatically
                await this.loadCart();
            } else {
                const error = await response.json();
                this.showNotification(error.error || 'Payment confirmation failed', 'error');
            }
        } catch (error) {
            console.error('Payment confirmation error:', error);
            this.showNotification('Error confirming payment', 'error');
        }
    }

    cancelPayment() {
        document.getElementById('qrModal').style.display = 'none';
        this.currentPaymentId = null;
    }

    showNotification(message, type = 'success') {
        const notification = document.getElementById('notification');
        const text = document.getElementById('notificationText');
        
        text.textContent = message;
        notification.style.background = type === 'error' ? 'var(--danger)' : 
                                       type === 'info' ? 'var(--primary)' : 
                                       'var(--success)';
        notification.style.display = 'block';
        
        setTimeout(() => {
            notification.style.display = 'none';
        }, 3000);
    }

    updateScannerStatus(status, connected) {
        document.getElementById('scannerStatus').textContent = status;
        const indicators = document.querySelectorAll('.status-indicator');
        indicators.forEach(ind => {
            ind.className = `status-indicator ${connected ? 'connected' : 'disconnected'}`;
        });
    }

    updateLastScan() {
        const now = new Date();
        const timeStr = now.toLocaleTimeString();
        document.getElementById('lastScan').textContent = timeStr;
    }

    updateClock() {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        const timeElement = document.getElementById('statTime');
        if (timeElement && !this.lastUpdate) {
            timeElement.textContent = timeStr;
        }
    }
}

// Initialize cart manager
let cartManager;

document.addEventListener('DOMContentLoaded', () => {
    cartManager = new CartManager();
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case 'r':
                    e.preventDefault();
                    cartManager.refreshCart();
                    break;
                case 'Delete':
                    e.preventDefault();
                    clearCart();
                    break;
                case 'Enter':
                    e.preventDefault();
                    if (!document.getElementById('checkoutBtn').disabled) {
                        proceedToCheckout();
                    }
                    break;
            }
        }
    });
});

// Global functions for onclick handlers
function clearCart() {
    cartManager.clearCart();
}

function proceedToCheckout() {
    cartManager.proceedToCheckout();
}

function cancelPayment() {
    cartManager.cancelPayment();
}

function confirmPaymentComplete() {
    cartManager.confirmPaymentComplete();
}
''',

    # Monitor page for system status
    "static/monitor.html": '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Monitor - Smart Checkout</title>
    <link rel="stylesheet" href="/static/css/style.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
</head>
<body>
    <div class="app-container">
        <header class="app-header">
            <div class="header-content">
                <h1>System Monitor</h1>
                <nav class="header-nav">
                    <button class="nav-btn" onclick="window.location.href='/'">
                        <i class="fas fa-home"></i> Home
                    </button>
                </nav>
            </div>
        </header>
        <main class="main-content">
            <div id="systemStatus">Loading...</div>
        </main>
    </div>
    <script>
        async function updateStatus() {
            const response = await fetch('/api/system-status');
            const data = await response.json();
            document.getElementById('systemStatus').innerHTML = `
                <pre>${JSON.stringify(data, null, 2)}</pre>
            `;
        }
        setInterval(updateStatus, 5000);
        updateStatus();
    </script>
</body>
</html>'''
}

# ============================================================================
# PART 2: ENHANCED PYQT FILES
# ============================================================================

PYQT_FILES = {
    # Enhanced ui/main_window.py with batch sending and better UX
    "ui/main_window.py": '''import sys
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
            empty_label = QLabel("Preview empty\nScanned items appear here")
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
            empty_label = QLabel("No items detected\nClick 📷 SCAN to detect products")
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
            msg.setText("Cannot connect to web server!\n\nMake sure the web server is running on port 8000")
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
        
        error_text = "\n".join(errors[:5])  # Show first 5 errors
        msg.setText(f"Failed to send items:\n\n{error_text}")
        msg.exec_()
    
    def show_connection_error(self):
        """Show connection error message"""
        msg = DarkMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Connection Error")
        msg.setText("Cannot connect to web server!\n\nPlease ensure the web server is running on port 8000")
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
        msg.setText("Checkout is handled through the web interface.\n\nPlease send items to web cart first.")
        msg.exec_()
    
    def closeEvent(self, event):
        """Clean up on close"""
        self.video_stream.stop()
        event.accept()
'''
}

# ============================================================================
# PART 3: SETUP SCRIPT
# ============================================================================

def create_setup_script():
    """Create the complete setup script"""
    
    print("\n" + "="*80)
    print("HYBRID SMART CHECKOUT SYSTEM - COMPLETE SETUP")
    print("="*80)
    
    # Try to find directories with multiple possible paths
    possible_web_dirs = [
        Path("smart-checkout-optimized"),
        Path("smart-checkout-complete"),
        Path("web-checkout-system")
    ]
    
    possible_pyqt_dirs = [
        Path("Hello/self-checkout-system"),
        Path("Hello\\self-checkout-system"),  # Windows path
        Path("self-checkout-system"),
        Path("pyqt-checkout-system")
    ]
    
    # Find web directory
    web_dir = None
    for dir_path in possible_web_dirs:
        if dir_path.exists():
            web_dir = dir_path
            break
    
    # Find PyQt directory
    pyqt_dir = None
    for dir_path in possible_pyqt_dirs:
        if dir_path.exists():
            pyqt_dir = dir_path
            break
    
    # If not found, list current directory contents to help user
    if not web_dir or not pyqt_dir:
        print("\n📁 Current directory contents:")
        current_dir = Path(".")
        for item in current_dir.iterdir():
            if item.is_dir():
                print(f"   📂 {item}")
                # Check subdirectories
                for subitem in item.iterdir():
                    if subitem.is_dir():
                        print(f"      📂 {subitem}")
        
        print("\n" + "="*80)
        
    if not web_dir:
        print(f"\n❌ Web directory not found!")
        print("Expected one of:")
        for dir_path in possible_web_dirs:
            print(f"   • {dir_path}")
        print("\nPlease ensure the web system exists first.")
        
        # Ask user for custom path
        user_path = input("\nEnter the path to your web system directory (or press Enter to exit): ").strip()
        if user_path:
            web_dir = Path(user_path)
            if not web_dir.exists():
                print(f"❌ Directory not found: {web_dir}")
                return False
        else:
            return False
    
    if not pyqt_dir:
        print(f"\n❌ PyQt directory not found!")
        print("Expected one of:")
        for dir_path in possible_pyqt_dirs:
            print(f"   • {dir_path}")
        print("\nPlease ensure the PyQt system exists first.")
        
        # Ask user for custom path
        user_path = input("\nEnter the path to your PyQt system directory (or press Enter to exit): ").strip()
        if user_path:
            pyqt_dir = Path(user_path)
            if not pyqt_dir.exists():
                print(f"❌ Directory not found: {pyqt_dir}")
                return False
        else:
            return False
    
    print("\n✅ Found both systems")
    print(f"   Web:  {web_dir}")
    print(f"   PyQt: {pyqt_dir}")
    
    # Backup existing files
    print("\n📦 Creating backups...")
    
    backup_files = [
        web_dir / "main.py",
        pyqt_dir / "ui" / "main_window.py"
    ]
    
    for file in backup_files:
        if file.exists():
            backup = file.with_suffix('.py.backup')
            shutil.copy(file, backup)
            print(f"   Backed up: {file.name} -> {backup.name}")
    
    # Write web files
    print("\n📝 Updating Web System...")
    
    for filename, content in WEB_FILES.items():
        filepath = web_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"   ✓ {filename}")
    
    # Write PyQt files
    print("\n📝 Updating PyQt System...")
    
    for filename, content in PYQT_FILES.items():
        filepath = pyqt_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"   ✓ {filename}")
    
    # Create startup scripts
    print("\n🚀 Creating startup scripts...")
    
    # Web startup script
    web_start = web_dir / "start_hybrid_web.sh"
    with open(web_start, 'w') as f:
        f.write('''#!/bin/bash
echo "Starting Hybrid Web Server..."
python main.py
''')
    os.chmod(web_start, 0o755)
    print(f"   ✓ {web_start.name}")
    
    # PyQt startup script
    pyqt_start = pyqt_dir / "start_hybrid_scanner.sh"
    with open(pyqt_start, 'w') as f:
        f.write('''#!/bin/bash
echo "Starting Hybrid PyQt Scanner..."
python main.py
''')
    os.chmod(pyqt_start, 0o755)
    print(f"   ✓ {pyqt_start.name}")
    
    # Combined startup script
    combined_start = Path("start_hybrid_system.sh")
    with open(combined_start, 'w') as f:
        f.write('''#!/bin/bash
echo "==============================================="
echo "Starting Hybrid Smart Checkout System"
echo "==============================================="

# Start web server in background
echo "Starting web server..."
cd smart-checkout-optimized
python main.py &
WEB_PID=$!

# Wait for web server to start
sleep 3

# Start PyQt scanner
echo "Starting PyQt scanner..."
cd ../Hello/self-checkout-system
python main.py

# When PyQt closes, kill web server
kill $WEB_PID
''')
    os.chmod(combined_start, 0o755)
    print(f"   ✓ {combined_start.name}")
    
    print("\n" + "="*80)
    print("✅ SETUP COMPLETE!")
    print("="*80)
    
    print("\n📋 NEXT STEPS:")
    print("\n1. Install required Python packages:")
    print("   pip install requests")
    print("\n2. Start the hybrid system:")
    print("\n   Option A - Start both together:")
    print("   ./start_hybrid_system.sh")
    print("\n   Option B - Start separately:")
    print("   Terminal 1: cd smart-checkout-optimized && python main.py")
    print("   Terminal 2: cd Hello/self-checkout-system && python main.py")
    
    print("\n🎯 USAGE FLOW:")
    print("   1. Scan products in PyQt (fast local detection)")
    print("   2. Click 'SEND TO WEB CART' button")
    print("   3. Open browser to http://localhost:8000/cart")
    print("   4. Complete payment with QR code")
    print("   5. Stock reduces automatically")
    
    print("\n✨ KEY FEATURES:")
    print("   • Batch sending for efficiency")
    print("   • Real-time WebSocket updates")
    print("   • Sound feedback")
    print("   • Connection status monitoring")
    print("   • Keyboard shortcuts (Ctrl+R refresh, Ctrl+Enter checkout)")
    print("   • Auto-cleanup of old carts")
    print("   • Session support for multiple users")
    print("   • Beautiful animated UI")
    
    print("\n🔗 WEB INTERFACE URLS:")
    print("   Cart:      http://localhost:8000/cart")
    print("   Inventory: http://localhost:8000/")
    print("   Analytics: http://localhost:8000/admin")
    print("   Monitor:   http://localhost:8000/monitor")
    
    print("\n" + "="*80)
    print("Happy scanning! 🛒")
    print("="*80 + "\n")
    
    return True

if __name__ == "__main__":
    create_setup_script()
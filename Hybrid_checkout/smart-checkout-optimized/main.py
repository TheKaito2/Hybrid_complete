from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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


def get_product_flexible(product_id: str):
    """Get product with flexible ID matching"""
    # Try exact match first
    product = db.get_product(product_id)  
    if product:
        return product
    
    # Try with dash/underscore variations
    variations = [
        product_id.replace('_', '-'),
        product_id.replace('-', '_'),
        product_id.lower(),
        product_id.lower().replace('_', '-'),
        product_id.lower().replace('-', '_')
    ]
    
    for variant in variations:
        product = db.get_product(variant)
        if product:
            return product
    
    # Try to find by partial match
    all_products = db.get_products()
    for p in all_products:
        if product_id.lower() in p['id'].lower():
            return p
        # Also check if the IDs are similar
        if p['id'].replace('-', '').replace('_', '').lower() == product_id.replace('-', '').replace('_', '').lower():
            return p
    
    return None

@app.post("/api/add-to-cart")
async def add_to_cart(item_data: dict):
    """Add scanned item from PyQt scanner to cart"""
    try:
        product_id = item_data.get("product_id")
        session_id = item_data.get("session_id", None)
        quantity = item_data.get("quantity", 1)
        
        # Validate product exists
        product = get_product_flexible(product_id)
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
            
            product = get_product_flexible(product_id)
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
    print("\n" + "="*60)
    print("🚀 HYBRID SMART CHECKOUT SYSTEM v3.0")
    print("="*60)
    print("\n📍 Access Points:")
    print("   Inventory: http://localhost:8000")
    print("   Cart:      http://localhost:8000/cart")
    print("   Analytics: http://localhost:8000/admin")
    print("   Monitor:   http://localhost:8000/monitor")
    print("\n🔧 API Endpoints:")
    print("   POST /api/add-to-cart     - Add single item")
    print("   POST /api/add-batch-to-cart - Add multiple items")
    print("   GET  /api/cart            - Get cart contents")
    print("   POST /api/checkout-cart   - Create payment")
    print("="*60 + "\n")
    
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

import json
import os
from datetime import datetime
from pathlib import Path
import threading
from typing import List, Dict, Optional

class JsonDatabase:
    def __init__(self, db_path: str = "products.json"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        if not os.path.exists(self.db_path):
            with open(self.db_path, 'w') as f:
                json.dump({"products": [], "sales": [], "pending_payments": {}, "settings": {"theme": "light"}}, f)
    
    def _read_db(self) -> dict:
        with self.lock:
            with open(self.db_path, 'r') as f:
                return json.load(f)
    
    def _write_db(self, data: dict):
        with self.lock:
            with open(self.db_path, 'w') as f:
                json.dump(data, f, indent=2)
    
    def get_products(self) -> List[Dict]:
        return self._read_db().get("products", [])
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        products = self.get_products()
        for product in products:
            if product["id"] == product_id:
                return product
        return None
    
    def get_product_by_yolo_class(self, yolo_class: str) -> Optional[Dict]:
        products = self.get_products()
        for product in products:
            if product.get("yolo_class") == yolo_class:
                return product
        return None
    
    def update_stock(self, product_id: str, quantity: int, operation: str = "add") -> bool:
        data = self._read_db()
        products = data.get("products", [])
        
        for i, product in enumerate(products):
            if product["id"] == product_id:
                if operation == "add":
                    products[i]["stock"] += quantity
                elif operation == "subtract":
                    if products[i]["stock"] >= quantity:
                        products[i]["stock"] -= quantity
                    else:
                        return False
                
                data["products"] = products
                self._write_db(data)
                return True
        
        return False
    
    def add_pending_payment(self, payment_id: str, payment_data: dict):
        data = self._read_db()
        if "pending_payments" not in data:
            data["pending_payments"] = {}
        
        data["pending_payments"][payment_id] = payment_data
        self._write_db(data)
    
    def get_pending_payment(self, payment_id: str) -> Optional[Dict]:
        data = self._read_db()
        return data.get("pending_payments", {}).get(payment_id)
    
    def process_pending_payment(self, payment_id: str) -> Optional[Dict]:
        data = self._read_db()
        pending_payment = data.get("pending_payments", {}).get(payment_id)
        
        if not pending_payment or pending_payment["status"] != "pending":
            return None
        
        sale = {
            "id": f"SALE-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "payment_id": payment_id,
            "timestamp": datetime.now().isoformat(),
            "items": pending_payment["items"],
            "subtotal": pending_payment["subtotal"],
            "tax": pending_payment["tax"],
            "total": pending_payment["total"],
            "payment_method": "qr_code"
        }
        
        products = data.get("products", [])
        for item in pending_payment["items"]:
            for i, product in enumerate(products):
                if product["id"] == item["product_id"]:
                    if products[i]["stock"] >= item["quantity"]:
                        products[i]["stock"] -= item["quantity"]
                    break
        
        data["pending_payments"][payment_id]["status"] = "completed"
        
        if "sales" not in data:
            data["sales"] = []
        data["sales"].append(sale)
        
        data["products"] = products
        self._write_db(data)
        
        return sale
    
    def get_sales(self, limit: int = 50) -> List[Dict]:
        data = self._read_db()
        sales = data.get("sales", [])
        return list(reversed(sales))[:limit]
    
    def get_settings(self) -> Dict:
        data = self._read_db()
        return data.get("settings", {})
    
    def get_theme(self) -> str:
        data = self._read_db()
        return data.get("settings", {}).get("theme", "light")
    
    def set_theme(self, theme: str):
        data = self._read_db()
        if "settings" not in data:
            data["settings"] = {}
        data["settings"]["theme"] = theme
        self._write_db(data)
    
    def get_analytics(self) -> Dict:
        data = self._read_db()
        sales = data.get("sales", [])
        products = data.get("products", [])
        
        today = datetime.now().date()
        today_sales = [s for s in sales if datetime.fromisoformat(s["timestamp"]).date() == today]
        
        product_sales = {}
        for sale in sales:
            for item in sale["items"]:
                pid = item["product_id"]
                if pid not in product_sales:
                    product_sales[pid] = {"quantity": 0, "revenue": 0}
                product_sales[pid]["quantity"] += item["quantity"]
                product_sales[pid]["revenue"] += item["total"]
        
        top_products = sorted(
            [(pid, data) for pid, data in product_sales.items()],
            key=lambda x: x[1]["revenue"],
            reverse=True
        )[:10]
        
        return {
            "total_sales": len(sales),
            "today_sales": len(today_sales),
            "today_revenue": sum(s["total"] for s in today_sales),
            "total_revenue": sum(s["total"] for s in sales),
            "top_products": [
                {
                    "product_id": pid,
                    "product_name": next((p["name"] for p in products if p["id"] == pid), "Unknown"),
                    "quantity_sold": data["quantity"],
                    "revenue": data["revenue"]
                }
                for pid, data in top_products
            ],
            "low_stock_count": len([p for p in products if p["stock"] <= p["min_stock"]])
        }

# product.py
from dataclasses import dataclass
from typing import Optional


@dataclass
class Product:
    """Product data model"""
    id: str
    name: str
    price: float
    category: str
    barcode: Optional[str] = None
    stock: int = 0
    image: Optional[str] = None
    description: Optional[str] = None
    weight: Optional[str] = None
    volume: Optional[str] = None
    yolo_class_name: Optional[str] = None
    
    def __str__(self):
        return f"{self.name} - ฿{self.price:.2f}"
    
    def is_in_stock(self) -> bool:
        """Check if product is in stock"""
        return self.stock > 0
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'category': self.category,
            'barcode': self.barcode,
            'stock': self.stock,
            'image': self.image,
            'description': self.description,
            'weight': self.weight,
            'volume': self.volume,
            'yolo_class_name': self.yolo_class_name
        }

# cart.py
from typing import List, Dict, Tuple
from collections import defaultdict
from datetime import datetime
from .product import Product


class CartItem:
    """Individual item in the shopping cart"""
    
    def __init__(self, product: Product, quantity: int = 1):
        self.product = product
        self.quantity = quantity
        self.added_at = datetime.now()
    
    @property
    def subtotal(self) -> float:
        """Calculate subtotal for this item"""
        return self.product.price * self.quantity
    
    def __str__(self):
        return f"{self.product.name} x{self.quantity} - ฿{self.subtotal:.2f}"


class ShoppingCart:
    """Shopping cart management"""
    
    def __init__(self, tax_rate: float = 0.07):
        self.items: Dict[str, CartItem] = {}  # product_id -> CartItem
        self.tax_rate = tax_rate
        self.created_at = datetime.now()
    
    def add_product(self, product: Product, quantity: int = 1) -> bool:
        """
        Add product to cart
        
        Args:
            product: Product to add
            quantity: Quantity to add
            
        Returns:
            True if successful, False if out of stock
        """
        if quantity > product.stock:
            return False
        
        if product.id in self.items:
            # Update quantity if product already in cart
            new_quantity = self.items[product.id].quantity + quantity
            if new_quantity > product.stock:
                return False
            self.items[product.id].quantity = new_quantity
        else:
            # Add new product to cart
            self.items[product.id] = CartItem(product, quantity)
        
        return True
    
    def remove_product(self, product_id: str) -> bool:
        """
        Remove product from cart
        
        Args:
            product_id: ID of product to remove
            
        Returns:
            True if removed, False if not found
        """
        if product_id in self.items:
            del self.items[product_id]
            return True
        return False
    
    def update_quantity(self, product_id: str, quantity: int) -> bool:
        """
        Update product quantity
        
        Args:
            product_id: Product ID
            quantity: New quantity (0 removes the item)
            
        Returns:
            True if successful
        """
        if product_id not in self.items:
            return False
        
        if quantity <= 0:
            return self.remove_product(product_id)
        
        if quantity > self.items[product_id].product.stock:
            return False
        
        self.items[product_id].quantity = quantity
        return True
    
    def clear(self) -> None:
        """Clear all items from cart"""
        self.items.clear()
    
    @property
    def subtotal(self) -> float:
        """Calculate subtotal (before tax)"""
        return sum(item.subtotal for item in self.items.values())
    
    @property
    def tax_amount(self) -> float:
        """Calculate tax amount"""
        return self.subtotal * self.tax_rate
    
    @property
    def total(self) -> float:
        """Calculate total (including tax)"""
        return self.subtotal + self.tax_amount
    
    @property
    def item_count(self) -> int:
        """Get total number of items in cart"""
        return sum(item.quantity for item in self.items.values())
    
    def get_items(self) -> List[CartItem]:
        """Get all items in cart"""
        return list(self.items.values())
    
    def get_summary(self) -> Dict[str, float]:
        """Get cart summary"""
        return {
            'subtotal': self.subtotal,
            'tax': self.tax_amount,
            'total': self.total,
            'item_count': self.item_count
        }
    
    def __len__(self):
        """Number of unique products in cart"""
        return len(self.items)
    
    def __str__(self):
        return f"Cart: {self.item_count} items - Total: ฿{self.total:.2f}"

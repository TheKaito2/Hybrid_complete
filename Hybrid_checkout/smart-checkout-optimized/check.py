# Create this as a test file: check_products.py
# Run it in the web server directory to see what product IDs are in the database

import json
import os

# Check products.json in web server
web_products_file = "products.json"
if os.path.exists(web_products_file):
    with open(web_products_file, 'r') as f:
        data = json.load(f)
        products = data.get('products', [])
        
        print("=== WEB SERVER PRODUCTS ===")
        for product in products:
            print(f"ID: {product['id']:<30} Name: {product['name']}")
        print()

# Check products.json in PyQt scanner
pyqt_products_file = "../self-checkout-system/database/products.json"
if os.path.exists(pyqt_products_file):
    with open(pyqt_products_file, 'r') as f:
        data = json.load(f)
        products_by_category = data.get('products', {})
        
        print("=== PYQT SCANNER PRODUCTS ===")
        for category, products in products_by_category.items():
            print(f"\nCategory: {category}")
            for product_id, product in products.items():
                yolo_class = product.get('yolo_class_name', 'N/A')
                print(f"  ID: {product_id:<25} YOLO: {yolo_class:<30} Name: {product['name']}")
        print()

print("\n=== EXPECTED WEB API FORMAT ===")
print("The web API expects product IDs in this format:")
print("- All lowercase")
print("- Dashes instead of underscores")
print("- Examples: 'chips-lays-nori', 'chips-snackjack-original', 'drinks-coca-cola-bottle'")
# Smart Self-Checkout System

A YOLO-based product detection system for convenience store self-checkout using Raspberry Pi 5 and touch display.

## Features

- Snapshot-based product detection using YOLO v8 (like taking a photo)
- JSON-based product database for easy management
- Multi-model support for different product categories
- Touch-friendly UI optimized for 1240x720 display
- Shopping cart with tax calculation and item deletion
- Delete buttons for both scanned items and cart items
- Dark-themed payment dialogs
- Modular architecture for easy extension

## Quick Start

1. Run the setup script:
   ```bash
   python setup_project.py
   ```

2. Copy your YOLO models:
   ```bash
   cp /path/to/your/chips_model.pt trained_models/
   cp /path/to/your/drinks_model.pt trained_models/
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python main.py
   ```

## How to Use

1. Click "📷 Scan!" to take a snapshot and detect products
2. Review detected items - use ❌ button to remove wrong items
3. Click "Add!" to add detected items to cart
4. In cart, use 🗑️ button to remove individual items
5. Click "Pay!" to checkout with dark-themed payment dialog

## Supported Products

### Chips:
- Lay's Flat Original Flavor
- Lay's Nori Seaweed Flavor
- Lay's Ridged Original Flavor
- Snackjack Original Flavor
- Tasto Japanese Seaweed Flavor
- Tasto Original Flavor
- Enter
- Atreus

### Drinks:
- Coca-Cola Bottle
- Coca-Cola Can
- Crystal Water
- Fanta Fruit Punch
- Pepsi
- Sprite

## Configuration

- Camera settings: `config/settings.json`
- Product database: `database/products.json`
- UI colors and fonts: `config/settings.json`

## Hardware Requirements

- Raspberry Pi 5
- Pi Touch Display 2 (1240x720)
- USB Camera or IP Camera
- Python 3.8+

## License

MIT License

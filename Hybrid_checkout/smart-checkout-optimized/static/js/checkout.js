// Checkout System
class CheckoutSystem {
    constructor() {
        this.ws = null;
        this.stream = null;
        this.video = null;
        this.canvas = null;
        this.ctx = null;
        this.detectedItems = new Map();
        this.cart = [];
        this.isDetecting = false;
        this.products = new Map();
        this.currentPaymentId = null;
        
        this.init();
    }

    async init() {
        this.video = document.getElementById('cameraVideo');
        this.canvas = document.getElementById('detectionCanvas');
        this.ctx = this.canvas.getContext('2d');
        
        await this.loadProducts();
        this.bindEvents();
        await this.initCamera();
        this.connectWebSocket();
    }

    async loadProducts() {
        try {
            const response = await fetch('/api/products');
            const products = await response.json();
            products.forEach(p => {
                if (p.yolo_class) {
                    this.products.set(p.yolo_class, p);
                }
            });
        } catch (error) {
            console.error('Error loading products:', error);
        }
    }

    bindEvents() {
        document.getElementById('toggleCamera').addEventListener('click', () => this.toggleCamera());
        document.getElementById('addToCartBtn').addEventListener('click', () => this.addDetectedToCart());
        document.getElementById('checkoutBtn').addEventListener('click', () => this.showPaymentQR());
    }

    async initCamera() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ video: true });
            this.video.srcObject = this.stream;
            
            await new Promise((resolve) => {
                this.video.onloadedmetadata = () => {
                    this.canvas.width = this.video.videoWidth;
                    this.canvas.height = this.video.videoHeight;
                    resolve();
                };
            });
            
            this.updateDetectionStatus('Camera ready', true);
            this.startDetection();
            
        } catch (error) {
            console.error('Camera error:', error);
            this.updateDetectionStatus('Camera error', false);
        }
    }

    connectWebSocket() {
        this.ws = new WebSocket(`ws://${window.location.host}/ws/detection`);
        
        this.ws.onopen = () => {
            this.isDetecting = true;
            this.updateDetectionStatus('Ready - Position products', true);
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'detections') {
                this.processDetections(data.data);
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateDetectionStatus('Connection error', false);
        };
        
        this.ws.onclose = () => {
            this.isDetecting = false;
            this.updateDetectionStatus('Disconnected', false);
            setTimeout(() => this.connectWebSocket(), 3000);
        };
    }

    startDetection() {
        const detectFrame = () => {
            if (this.isDetecting && this.ws && this.ws.readyState === WebSocket.OPEN) {
                try {
                    const tempCanvas = document.createElement('canvas');
                    tempCanvas.width = this.video.videoWidth;
                    tempCanvas.height = this.video.videoHeight;
                    const tempCtx = tempCanvas.getContext('2d');
                    tempCtx.drawImage(this.video, 0, 0);
                    
                    const frameData = tempCanvas.toDataURL('image/jpeg', 0.8);
                    
                    this.ws.send(JSON.stringify({
                        type: 'frame',
                        frame: frameData
                    }));
                } catch (err) {
                    console.error('Error capturing frame:', err);
                }
            }
            
            setTimeout(detectFrame, 100);
        };
        
        detectFrame();
    }

    processDetections(detections) {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.detectedItems.clear();
        
        detections.forEach(detection => {
            const { bbox, confidence, product } = detection;
            
            if (product) {
                this.detectedItems.set(product.id, {
                    ...product,
                    confidence: confidence
                });
                
                this.drawBoundingBox(bbox, product.name, confidence);
            }
        });
        
        this.updateDetectedItemsDisplay();
        
        const status = detections.length > 0 
            ? `Detecting ${detections.length} item${detections.length !== 1 ? 's' : ''}`
            : 'Ready - Position products';
        this.updateDetectionStatus(status, true);
    }

    drawBoundingBox(bbox, label, confidence) {
        const { x1, y1, x2, y2 } = bbox;
        
        this.ctx.strokeStyle = '#0066FF';
        this.ctx.lineWidth = 3;
        this.ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        
        this.ctx.fillStyle = '#0066FF';
        this.ctx.fillRect(x1, y1 - 25, 200, 25);
        
        this.ctx.fillStyle = 'white';
        this.ctx.font = 'bold 14px Arial';
        this.ctx.fillText(`${label} (${Math.round(confidence * 100)}%)`, x1 + 5, y1 - 7);
    }

    updateDetectedItemsDisplay() {
        const container = document.getElementById('detectedItems');
        
        if (this.detectedItems.size === 0) {
            container.innerHTML = '<p style="text-align: center; color: var(--text-secondary);">Position products in camera view</p>';
            document.getElementById('addToCartBtn').disabled = true;
            return;
        }
        
        container.innerHTML = Array.from(this.detectedItems.values()).map(item => `
            <div style="padding: 0.75rem; background: var(--bg-tertiary); border-radius: 0.5rem; margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-weight: 500;">${item.name}</div>
                    <div style="color: var(--text-secondary); font-size: 0.875rem;">฿${item.price.toFixed(2)}</div>
                </div>
                <span style="padding: 0.25rem 0.5rem; background: var(--bg-secondary); border-radius: 0.25rem; font-size: 0.75rem; color: var(--text-secondary);">${Math.round(item.confidence * 100)}%</span>
            </div>
        `).join('');
        
        document.getElementById('addToCartBtn').disabled = false;
    }

    addDetectedToCart() {
        this.detectedItems.forEach(item => {
            const existingItem = this.cart.find(cartItem => cartItem.id === item.id);
            
            if (existingItem) {
                existingItem.quantity++;
            } else {
                this.cart.push({
                    ...item,
                    quantity: 1
                });
            }
        });
        
        this.detectedItems.clear();
        this.updateDetectedItemsDisplay();
        this.updateCartDisplay();
    }

    updateCartDisplay() {
        const container = document.getElementById('cartItems');
        
        if (this.cart.length === 0) {
            container.innerHTML = `
                <div class="empty-cart">
                    <i class="fas fa-shopping-cart" style="font-size: 3rem; margin-bottom: 1rem;"></i>
                    <p>Your cart is empty</p>
                </div>
            `;
            document.getElementById('checkoutBtn').disabled = true;
            this.updateCartSummary(0, 0, 0);
            return;
        }
        
        container.innerHTML = this.cart.map((item, index) => `
            <div style="padding: 1rem; background: var(--bg-tertiary); border-radius: 0.5rem; margin-bottom: 0.75rem;">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.5rem;">
                    <span style="font-weight: 500;">${item.name}</span>
                    <span style="color: var(--danger); cursor: pointer; font-size: 0.875rem;" onclick="checkoutSystem.removeFromCart(${index})">
                        <i class="fas fa-times"></i>
                    </span>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; color: var(--text-secondary); font-size: 0.875rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <button style="width: 1.5rem; height: 1.5rem; border: 1px solid var(--border); background: var(--bg-primary); border-radius: 0.25rem; cursor: pointer;" onclick="checkoutSystem.updateQuantity(${index}, -1)">-</button>
                        <span>${item.quantity}</span>
                        <button style="width: 1.5rem; height: 1.5rem; border: 1px solid var(--border); background: var(--bg-primary); border-radius: 0.25rem; cursor: pointer;" onclick="checkoutSystem.updateQuantity(${index}, 1)">+</button>
                    </div>
                    <span>฿${(item.price * item.quantity).toFixed(2)}</span>
                </div>
            </div>
        `).join('');
        
        document.getElementById('checkoutBtn').disabled = false;
        this.updateCartSummary();
    }

    updateQuantity(index, change) {
        const item = this.cart[index];
        item.quantity += change;
        
        if (item.quantity <= 0) {
            this.removeFromCart(index);
        } else {
            this.updateCartDisplay();
        }
    }

    removeFromCart(index) {
        this.cart.splice(index, 1);
        this.updateCartDisplay();
    }

    updateCartSummary() {
        const subtotal = this.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
        const tax = subtotal * 0.07;
        const total = subtotal + tax;
        
        document.getElementById('subtotal').textContent = `฿${subtotal.toFixed(2)}`;
        document.getElementById('tax').textContent = `฿${tax.toFixed(2)}`;
        document.getElementById('total').textContent = `฿${total.toFixed(2)}`;
    }

    async showPaymentQR() {
        if (this.cart.length === 0) return;
        
        const checkoutData = {
            items: this.cart.map(item => ({
                product_id: item.id,
                quantity: item.quantity
            }))
        };
        
        try {
            const response = await fetch('/api/create-payment', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(checkoutData)
            });
            
            if (response.ok) {
                const payment = await response.json();
                this.currentPaymentId = payment.payment_id;
                
                document.getElementById('qrImage').src = payment.qr_code;
                document.getElementById('paymentAmount').textContent = `฿${payment.total.toFixed(2)}`;
                document.getElementById('qrModal').style.display = 'block';
            } else {
                const error = await response.json();
                alert(error.error || 'Failed to create payment');
            }
        } catch (error) {
            console.error('Checkout error:', error);
            alert('Error creating payment');
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
                this.showSuccessModal(sale);
                this.cart = [];
                this.currentPaymentId = null;
            } else {
                const error = await response.json();
                alert(error.error || 'Payment confirmation failed');
            }
        } catch (error) {
            console.error('Payment confirmation error:', error);
            alert('Error confirming payment');
        }
    }

    async cancelPayment() {
        document.getElementById('qrModal').style.display = 'none';
        this.currentPaymentId = null;
    }

    showSuccessModal(sale) {
        document.getElementById('receiptNumber').textContent = `Receipt: ${sale.id}`;
        document.getElementById('successModal').style.display = 'block';
    }

    resetCheckout() {
        this.cart = [];
        this.currentPaymentId = null;
        this.updateCartDisplay();
        document.getElementById('successModal').style.display = 'none';
    }

    toggleCamera() {
        if (this.stream) {
            const tracks = this.stream.getTracks();
            tracks.forEach(track => {
                track.enabled = !track.enabled;
            });
            
            const btn = document.getElementById('toggleCamera');
            btn.innerHTML = tracks[0].enabled ? 
                '<i class="fas fa-video"></i>' : 
                '<i class="fas fa-video-slash"></i>';
        }
    }

    updateDetectionStatus(text, isActive) {
        document.getElementById('detectionText').textContent = text;
        const statusIcon = document.querySelector('.fa-circle');
        if (statusIcon) {
            statusIcon.style.color = isActive ? 'var(--success)' : 'var(--text-secondary)';
        }
    }
}

let checkoutSystem;

document.addEventListener('DOMContentLoaded', () => {
    checkoutSystem = new CheckoutSystem();
});

function resetCheckout() {
    checkoutSystem.resetCheckout();
}

function cancelPayment() {
    checkoutSystem.cancelPayment();
}

function confirmPaymentComplete() {
    checkoutSystem.confirmPaymentComplete();
}

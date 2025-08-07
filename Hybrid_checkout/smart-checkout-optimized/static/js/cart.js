// Enhanced Cart Management System
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

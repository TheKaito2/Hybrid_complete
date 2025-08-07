// Inventory Management
class InventoryManager {
    constructor() {
        this.products = [];
        this.currentFilter = 'all';
        this.searchQuery = '';
        this.selectedProductId = null;
        this.init();
    }

    async init() {
        this.bindEvents();
        await this.loadData();
        setInterval(() => this.loadData(), 30000);
    }

    bindEvents() {
        document.getElementById('searchInput').addEventListener('input', (e) => {
            this.searchQuery = e.target.value.toLowerCase();
            this.renderProducts();
        });

        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.filter-btn').forEach(b => {
                    b.classList.remove('active');
                    b.style.background = 'var(--bg-tertiary)';
                    b.style.color = 'var(--text-primary)';
                });
                btn.classList.add('active');
                btn.style.background = 'var(--primary)';
                btn.style.color = 'white';
                this.currentFilter = btn.dataset.filter;
                this.renderProducts();
            });
        });
    }

    async loadData() {
        try {
            const productsRes = await fetch('/api/products');
            this.products = await productsRes.json();

            const analyticsRes = await fetch('/api/analytics');
            const analytics = await analyticsRes.json();

            document.getElementById('totalProducts').textContent = this.products.length;
            document.getElementById('lowStockCount').textContent = analytics.low_stock_count;
            document.getElementById('todayRevenue').textContent = `฿${analytics.today_revenue.toFixed(2)}`;

            this.renderProducts();
        } catch (error) {
            console.error('Error loading data:', error);
        }
    }

    renderProducts() {
        const tbody = document.getElementById('productsTableBody');
        
        let filteredProducts = this.products;
        
        if (this.currentFilter !== 'all') {
            filteredProducts = filteredProducts.filter(p => p.category === this.currentFilter);
        }
        
        if (this.searchQuery) {
            filteredProducts = filteredProducts.filter(p => 
                p.name.toLowerCase().includes(this.searchQuery) ||
                p.category.toLowerCase().includes(this.searchQuery)
            );
        }

        tbody.innerHTML = filteredProducts.map(product => `
            <tr>
                <td>
                    <div style="display: flex; align-items: center; gap: 0.75rem;">
                        <div style="width: 2.5rem; height: 2.5rem; background: var(--bg-tertiary); border-radius: 0.5rem; display: flex; align-items: center; justify-content: center; color: var(--text-secondary);">
                            <i class="fas fa-box"></i>
                        </div>
                        <div>${product.name}</div>
                    </div>
                </td>
                <td>${product.category}</td>
                <td>฿${product.price.toFixed(2)}</td>
                <td>${product.stock}</td>
                <td>
                    <span class="status-badge ${this.getStatusClass(product)}">
                        ${this.getStatusText(product)}
                    </span>
                </td>
                <td>
                    <button class="btn btn-secondary" onclick="inventoryManager.showRestockModal('${product.id}')">
                        <i class="fas fa-plus"></i> Restock
                    </button>
                </td>
            </tr>
        `).join('');
    }

    getStatusClass(product) {
        if (product.stock === 0) return 'status-out';
        if (product.stock <= product.min_stock) return 'status-low';
        return 'status-good';
    }

    getStatusText(product) {
        if (product.stock === 0) return 'Out of Stock';
        if (product.stock <= product.min_stock) return 'Low Stock';
        return 'In Stock';
    }

    showRestockModal(productId) {
        const product = this.products.find(p => p.id === productId);
        if (!product) return;

        this.selectedProductId = productId;
        document.getElementById('restockProductName').textContent = product.name;
        document.getElementById('restockQuantity').value = '';
        document.getElementById('restockModal').style.display = 'block';
        document.getElementById('restockQuantity').focus();
    }

    async confirmRestock() {
        const quantity = parseInt(document.getElementById('restockQuantity').value);
        if (!quantity || quantity <= 0) {
            alert('Please enter a valid quantity');
            return;
        }

        try {
            const response = await fetch(`/api/restock/${this.selectedProductId}?quantity=${quantity}`, {
                method: 'POST'
            });

            if (response.ok) {
                this.closeRestockModal();
                await this.loadData();
            } else {
                alert('Failed to restock product');
            }
        } catch (error) {
            console.error('Error restocking:', error);
            alert('Error restocking product');
        }
    }

    closeRestockModal() {
        document.getElementById('restockModal').style.display = 'none';
        this.selectedProductId = null;
    }
}

function closeRestockModal() {
    window.inventoryManager.closeRestockModal();
}

function confirmRestock() {
    window.inventoryManager.confirmRestock();
}

document.addEventListener('DOMContentLoaded', () => {
    window.inventoryManager = new InventoryManager();
});
// Analytics Dashboard
class AdminDashboard {
    constructor() {
        this.analytics = null;
        this.init();
    }

    async init() {
        await this.loadAnalytics();
        await this.loadRecentTransactions();
        setInterval(() => {
            this.loadAnalytics();
            this.loadRecentTransactions();
        }, 30000);
    }

    async loadAnalytics() {
        try {
            const response = await fetch('/api/analytics');
            this.analytics = await response.json();
            this.updateMetrics();
            this.createBestSellersRanking();
        } catch (error) {
            console.error('Error loading analytics:', error);
        }
    }

    updateMetrics() {
        const { analytics } = this;
        
        document.getElementById('totalRevenue').textContent = `฿${analytics.total_revenue.toFixed(2)}`;
        document.getElementById('todaySales').textContent = analytics.today_sales;
        
        const avgOrder = analytics.total_sales > 0 ? 
            analytics.total_revenue / analytics.total_sales : 0;
        document.getElementById('avgOrder').textContent = `฿${avgOrder.toFixed(2)}`;
        
        // Simple growth calculation
        fetch('/api/sales?limit=100')
            .then(response => response.json())
            .then(sales => {
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                const yesterday = new Date(today);
                yesterday.setDate(yesterday.getDate() - 1);
                
                let todayRevenue = 0;
                let yesterdayRevenue = 0;
                
                sales.forEach(sale => {
                    const saleDate = new Date(sale.timestamp);
                    saleDate.setHours(0, 0, 0, 0);
                    
                    if (saleDate.getTime() === today.getTime()) {
                        todayRevenue += sale.total;
                    } else if (saleDate.getTime() === yesterday.getTime()) {
                        yesterdayRevenue += sale.total;
                    }
                });
                
                let growth = 0;
                if (yesterdayRevenue > 0) {
                    growth = ((todayRevenue - yesterdayRevenue) / yesterdayRevenue) * 100;
                } else if (todayRevenue > 0) {
                    growth = 100;
                }
                
                const growthElement = document.getElementById('revenueGrowth');
                const growthContainer = document.getElementById('growthContainer');
                
                growthElement.textContent = `${Math.abs(growth).toFixed(1)}%`;
                
                const arrow = growthContainer.querySelector('i');
                if (growth >= 0) {
                    arrow.className = 'fas fa-arrow-up';
                    growthContainer.style.color = 'var(--success)';
                } else {
                    arrow.className = 'fas fa-arrow-down';
                    growthContainer.style.color = 'var(--danger)';
                }
            });
    }

    createBestSellersRanking() {
        const container = document.getElementById('bestSellersRanking');
        
        if (!this.analytics || this.analytics.total_sales === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 3rem; color: var(--text-secondary);">
                    <i class="fas fa-trophy" style="font-size: 3rem; margin-bottom: 1rem; opacity: 0.3;"></i>
                    <p>No sales data yet</p>
                </div>
            `;
            return;
        }
        
        const topProducts = this.analytics.top_products.slice(0, 10);
        
        container.innerHTML = topProducts.map((product, index) => {
            const rank = index + 1;
            let rankClass = '';
            let rankIcon = rank;
            
            if (rank === 1) {
                rankClass = 'gold';
                rankIcon = '🥇';
            } else if (rank === 2) {
                rankClass = 'silver';
                rankIcon = '🥈';
            } else if (rank === 3) {
                rankClass = 'bronze';
                rankIcon = '🥉';
            }
            
            return `
                <div class="best-seller-item">
                    <div class="best-seller-rank ${rankClass}">${rankIcon}</div>
                    <div style="flex: 1;">
                        <div style="font-weight: 600; margin-bottom: 0.25rem;">${product.product_name}</div>
                        <div style="display: flex; gap: 1rem; font-size: 0.875rem; color: var(--text-secondary);">
                            <span>📦 ${product.quantity_sold} units</span>
                            <span>💰 ฿${product.revenue.toFixed(2)}</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    async loadRecentTransactions() {
        try {
            const response = await fetch('/api/sales?limit=10');
            const sales = await response.json();
            
            const container = document.getElementById('recentTransactions');
            
            if (sales.length === 0) {
                container.innerHTML = '<p style="text-align: center; color: var(--text-secondary);">No transactions yet</p>';
                return;
            }
            
            container.innerHTML = sales.map(sale => {
                const date = new Date(sale.timestamp);
                return `
                    <div style="padding: 1rem; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-weight: 500; font-size: 0.875rem;">${sale.id}</div>
                            <div style="color: var(--text-secondary); font-size: 0.75rem;">${date.toLocaleString()}</div>
                        </div>
                        <div style="font-weight: 600; color: var(--primary);">฿${sale.total.toFixed(2)}</div>
                    </div>
                `;
            }).join('');
        } catch (error) {
            console.error('Error loading transactions:', error);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new AdminDashboard();
});
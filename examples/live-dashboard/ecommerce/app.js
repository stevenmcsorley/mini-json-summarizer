/**
 * E-Commerce Frontend Application
 * Demonstrates real-world error scenarios with Mini JSON Summarizer
 */

const API_BASE = 'http://localhost:8000';
let cart = [];

// Sample products
const products = [
    { id: 1, name: 'Wireless Mouse', price: 29.99, emoji: '🖱️', stock: 15 },
    { id: 2, name: 'Mechanical Keyboard', price: 89.99, emoji: '⌨️', stock: 8 },
    { id: 3, name: 'USB-C Hub', price: 45.50, emoji: '🔌', stock: 0 }, // Out of stock
    { id: 4, name: 'Laptop Stand', price: 34.99, emoji: '💻', stock: 12 },
    { id: 5, name: 'Webcam HD', price: 59.99, emoji: '📹', stock: 5 },
    { id: 6, name: 'Headphones', price: 79.99, emoji: '🎧', stock: 20 },
    { id: 7, name: 'Monitor 27"', price: 299.99, emoji: '🖥️', stock: 3 },
    { id: 8, name: 'Cable Organizer', price: 12.99, emoji: '📦', stock: 50 }
];

// Initialize
window.addEventListener('DOMContentLoaded', () => {
    renderProducts();
    updateCartUI();
});

// Render product grid
function renderProducts() {
    const grid = document.getElementById('products-grid');
    grid.innerHTML = products.map(product => `
        <div class="product-card bg-white rounded-xl p-6 shadow-sm hover:shadow-md border border-gray-200">
            <div class="text-6xl mb-4 text-center">${product.emoji}</div>
            <h3 class="text-lg font-semibold mb-2">${product.name}</h3>
            <p class="text-2xl font-bold text-purple-600 mb-3">$${product.price}</p>
            <p class="text-sm text-gray-500 mb-4">
                ${product.stock > 0 ? `${product.stock} in stock` : '❌ Out of stock'}
            </p>
            <button
                onclick="addToCart(${product.id})"
                class="w-full bg-purple-600 text-white py-2 rounded-lg font-semibold hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
                ${product.stock === 0 ? 'disabled' : ''}
            >
                ${product.stock > 0 ? 'Add to Cart' : 'Out of Stock'}
            </button>
        </div>
    `).join('');
}

// Add to cart
async function addToCart(productId) {
    const product = products.find(p => p.id === productId);
    if (!product || product.stock === 0) {
        showToast('❌ Product not available', 'error');
        return;
    }

    try {
        // Call backend API - this may fail intentionally
        const response = await fetch(`${API_BASE}/api/cart/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: productId, quantity: 1 })
        });

        if (response.ok) {
            cart.push({ ...product, quantity: 1 });
            updateCartUI();
            showToast(`✅ ${product.name} added to cart`, 'success');
        } else {
            const error = await response.json();
            showToast(`❌ ${error.message || 'Failed to add to cart'}`, 'error');
        }
    } catch (error) {
        showToast('❌ Network error - check monitoring dashboard', 'error');
    }
}

// View cart
function viewCart() {
    const cartSummary = document.getElementById('cart-summary');
    const cartItems = document.getElementById('cart-items');

    if (cart.length === 0) {
        cartItems.innerHTML = '<p class="text-gray-500 text-center py-8">Your cart is empty</p>';
    } else {
        cartItems.innerHTML = cart.map((item, index) => `
            <div class="flex items-center justify-between border-b pb-4">
                <div class="flex items-center space-x-4">
                    <span class="text-3xl">${item.emoji}</span>
                    <div>
                        <p class="font-semibold">${item.name}</p>
                        <p class="text-sm text-gray-500">Qty: ${item.quantity}</p>
                    </div>
                </div>
                <div class="flex items-center space-x-4">
                    <p class="font-bold">$${item.price}</p>
                    <button onclick="removeFromCart(${index})" class="text-red-500 hover:text-red-700">
                        🗑️
                    </button>
                </div>
            </div>
        `).join('');
    }

    const total = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    document.getElementById('cart-total').textContent = `$${total.toFixed(2)}`;

    cartSummary.classList.remove('hidden');
}

// Close cart
function closeCart() {
    document.getElementById('cart-summary').classList.add('hidden');
}

// Remove from cart
function removeFromCart(index) {
    cart.splice(index, 1);
    updateCartUI();
    viewCart(); // Refresh cart view
}

// Checkout
async function checkout() {
    if (cart.length === 0) {
        showToast('❌ Cart is empty', 'error');
        return;
    }

    const total = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

    try {
        const response = await fetch(`${API_BASE}/api/checkout`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                items: cart,
                total: total,
                payment_method: 'credit_card'
            })
        });

        if (response.ok) {
            const result = await response.json();
            showToast(`✅ Order ${result.order_id} placed successfully!`, 'success');
            cart = [];
            updateCartUI();
            closeCart();
        } else {
            const error = await response.json();
            showToast(`❌ Checkout failed: ${error.message}`, 'error');
        }
    } catch (error) {
        showToast('❌ Checkout error - check monitoring dashboard', 'error');
    }
}

// Update cart UI
function updateCartUI() {
    const cartCount = document.getElementById('cart-count');
    cartCount.textContent = cart.length;
}

// Show toast notification
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toast-message');

    toastMessage.textContent = message;
    toast.className = `fixed bottom-4 right-4 px-6 py-4 rounded-lg shadow-lg ${
        type === 'success' ? 'bg-green-600 text-white' :
        type === 'error' ? 'bg-red-600 text-white' :
        'bg-gray-800 text-white'
    }`;
    toast.classList.remove('hidden');

    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

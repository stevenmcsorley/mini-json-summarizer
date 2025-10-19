# 🛒 E-Commerce Error Monitoring Demo

**Real-world demonstration** of Mini JSON Summarizer with a complete e-commerce application and error monitoring dashboard.

## ✨ What You'll See

1. **E-Commerce Store** (`http://localhost:3000`) - Real shopping experience with products, cart, checkout
2. **Monitoring Dashboard** (`http://localhost:3001`) - Real-time error tracking powered by Mini JSON Summarizer
3. **Intentional Errors** - Backend fails 30-40% of the time to demonstrate error monitoring
4. **AI-Powered Summaries** - Natural language insights from error logs

---

## 🚀 Quick Start

```bash
# From examples/live-dashboard directory
docker-compose up --build

# Open in your browser:
# - E-Commerce:  http://localhost:3000
# - Monitoring:  http://localhost:3001
```

**That's it!** Start shopping and watch errors appear in the monitoring dashboard.

---

## 🎯 How To Use

### 1. **Shop on E-Commerce Site**
- Browse 8 products (mouse, keyboard, webcam, etc.)
- Click "Add to Cart" buttons
- Proceed to checkout
- **30-40% of requests will fail** (intentionally)

### 2. **Watch Monitoring Dashboard**
- Open `http://localhost:3001` in another tab/window
- Click "🔄 Refresh Now" button
- See:
  - Total logs and error counts
  - Top error codes (500, 409, 503, etc.)
  - Error types (payment_error, inventory_error, etc.)
  - AI-generated summary from Mini JSON Summarizer
  - Recent log stream

### 3. **Compare Side-by-Side**
- Put e-commerce site on left half of screen
- Put monitoring dashboard on right half
- Click "Add to Cart" → Click "Refresh Now" → See errors appear!

---

## 📦 Architecture

```
┌──────────────────┐
│  E-Commerce      │  (Products, Cart, Checkout)
│  Frontend :3000  │  User clicks "Buy"
└────────┬─────────┘
         │ HTTP
         ▼
┌──────────────────┐
│  E-Commerce API  │  (30-40% failure rate)
│  Backend :8000   │  Intentional errors
└────────┬─────────┘
         │ Fluentd forward
         ▼
┌──────────────────┐
│   Fluentd        │  (Log aggregation)
│   :24224         │
└────────┬─────────┘
         │ HTTP POST
         ▼
┌──────────────────┐
│  Log Aggregator  │  (5-minute buffer)
│  :9880           │  GET /logs/last-5min
└────────┬─────────┘
         │ json param
         ▼
┌──────────────────┐
│ Mini JSON        │  (Profile: logs)
│ Summarizer :8080 │  AI insights
└────────┬─────────┘
         │ API response
         ▼
┌──────────────────┐
│  Monitoring      │  (Manual refresh)
│  Dashboard :3001 │  Shows errors
└──────────────────┘
```

---

## 🎭 Error Scenarios

### Cart Errors (30% failure rate)
- **500**: Database connection timeout
- **409**: Product out of stock
- **400**: Invalid product ID
- **503**: Cart service unavailable

### Checkout Errors (40% failure rate)
- **402**: Payment processing failed
- **409**: Items no longer available
- **403**: Fraud detection blocked transaction
- **504**: Payment gateway timeout
- **500**: Internal server error

### Success Case
- **200**: Operation completed successfully

---

## 📊 Monitoring Dashboard Features

### Top Stats
- **Total Logs**: All requests (success + errors)
- **Error Count**: Failed requests
- **Success Rate**: Percentage of successful operations
- **Most Common Error**: HTTP code appearing most frequently

### Charts
- **Top Error Codes**: Bar chart of HTTP status codes
- **Error Types**: Distribution of error categories
- **Recent Logs**: Last 20 log entries with timestamps

### AI Summary
- Powered by **Mini JSON Summarizer** `logs` profile
- Natural language insights from error patterns
- Automatic categorization and statistics

---

## 🛠️ Configuration

Edit `docker-compose.yml` to adjust error rates:

```yaml
ecommerce-api:
  environment:
    CART_ERROR_RATE: "0.30"      # 30% of cart requests fail
    CHECKOUT_ERROR_RATE: "0.40"  # 40% of checkouts fail
```

Set to `"0.00"` for 100% success rate (no errors).

---

## 🎬 Demo Flow

1. **Start the stack**: `docker-compose up`
2. **Open e-commerce**: http://localhost:3000
3. **Open monitoring**: http://localhost:3001 (in another tab)
4. **Click "Add to Cart"** on several products
5. **Click "Refresh Now"** on monitoring dashboard
6. **See errors appear** with AI-generated insights
7. **Try checkout** to trigger payment errors
8. **Refresh dashboard** again to see new errors

---

## 🔧 Troubleshooting

**Dashboard shows "No logs"?**
- Make sure you clicked "Add to Cart" in the e-commerce site first
- Click "Refresh Now" button on monitoring dashboard
- Check console for errors (F12)

**Can't add items to cart?**
- Check that ecommerce-api is running: `docker-compose logs ecommerce-api`
- Verify port 8000 is not blocked

**Summarizer errors?**
- Check that summarizer built successfully
- View logs: `docker-compose logs summarizer`
- Ensure profiles are loaded

---

## 📄 Files

```
live-dashboard/
├── ecommerce/              # E-commerce frontend
│   ├── index.html          # Product catalog, cart UI
│   └── app.js              # Shopping logic
├── ecommerce-api/          # Backend API
│   ├── server.py           # FastAPI with intentional errors
│   └── Dockerfile
├── monitoring/             # Error monitoring dashboard
│   ├── index.html          # Dashboard UI
│   └── app.js              # Fetch logs + summarize
├── log-aggregator/         # Log buffering service
│   ├── server.py           # Simple HTTP buffer
│   └── Dockerfile
├── logging/fluentd/        # Log collection
│   └── fluent.conf
└── docker-compose.yml      # Complete stack
```

---

## 🎯 Key Differences from Complex Version

**What Changed:**
- ✅ **No polling** - Manual refresh button only
- ✅ **No SSE streaming** - Simple POST requests
- ✅ **Real frontend** - Actual e-commerce UI with buttons
- ✅ **Simplified flow** - Click → Error → Refresh → See
- ✅ **No PC slowdown** - Removed resource-intensive polling loop
- ✅ **Stable charts** - No infinite vertical expansion
- ✅ **Better demo** - Actually shows real-world use case

---

## 📝 License

MIT © 2025 Steven McSorley

#!/bin/bash
# Continuous load generator for realistic traffic patterns

echo "🚀 Starting continuous load test..."
echo "📊 Dashboard: http://localhost:3000"
echo "Press Ctrl+C to stop"
echo ""

# Function to generate normal traffic
generate_traffic() {
  while true; do
    # API service traffic
    curl -s http://localhost:8081/api/users > /dev/null &
    curl -s http://localhost:8081/api/products/$(( RANDOM % 100 )) > /dev/null &

    # Auth service traffic
    curl -s -X POST http://localhost:8082/auth/login > /dev/null &

    # Worker service traffic
    curl -s -X POST http://localhost:8083/jobs/process > /dev/null &

    # Random delay between 0.5-2 seconds
    sleep $(awk -v min=0.5 -v max=2 'BEGIN{srand(); print min+rand()*(max-min)}')
  done
}

# Trap Ctrl+C
trap 'echo ""; echo "⏹️  Stopping load test..."; exit 0' INT

# Start traffic generation
generate_traffic

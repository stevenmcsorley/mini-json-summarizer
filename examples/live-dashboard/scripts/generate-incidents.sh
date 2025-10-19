#!/bin/bash
# Incident simulation script for live dashboard demo

set -e

INCIDENT_TYPE=${1:-"spike-504"}

echo "🔥 Generating incident: $INCIDENT_TYPE"

case $INCIDENT_TYPE in
  spike-504)
    echo "Simulating 504 Gateway Timeout spike..."
    for i in {1..50}; do
      curl -s http://localhost:8081/api/users > /dev/null &
      curl -s http://localhost:8081/api/orders > /dev/null &
    done
    wait
    echo "✅ Generated 100 requests (expect ~15% errors = 15 failures)"
    ;;

  token-expiry-wave)
    echo "Simulating gradual token expiry wave..."
    for round in {1..5}; do
      echo "Round $round/5..."
      for i in {1..20}; do
        curl -s http://localhost:8082/auth/verify > /dev/null &
        curl -s http://localhost:8082/auth/refresh > /dev/null &
      done
      wait
      sleep 2
    done
    echo "✅ Generated rolling auth failures"
    ;;

  total-failure)
    echo "Simulating total system failure..."
    for i in {1..100}; do
      curl -s http://localhost:8081/api/users > /dev/null &
      curl -s http://localhost:8082/auth/login > /dev/null &
      curl -s http://localhost:8083/jobs/process > /dev/null &
    done
    wait
    echo "✅ Generated catastrophic failure across all services"
    ;;

  slow-leak)
    echo "Simulating slow memory/queue leak..."
    for i in {1..30}; do
      curl -s -X POST http://localhost:8083/jobs/schedule > /dev/null &
      sleep 0.5
    done
    wait
    echo "✅ Simulated queue buildup"
    ;;

  auth-storm)
    echo "Simulating auth service overload..."
    for i in {1..80}; do
      curl -s -X POST http://localhost:8082/auth/login > /dev/null &
      curl -s -X POST http://localhost:8082/auth/verify \
        -H "Authorization: invalid-token" > /dev/null &
    done
    wait
    echo "✅ Generated auth storm"
    ;;

  *)
    echo "Unknown incident type: $INCIDENT_TYPE"
    echo ""
    echo "Available incidents:"
    echo "  spike-504          - Gateway timeout spike (API service)"
    echo "  token-expiry-wave  - Rolling auth failures"
    echo "  total-failure      - All services critical"
    echo "  slow-leak          - Queue/memory leak simulation"
    echo "  auth-storm         - Auth service overload"
    exit 1
    ;;
esac

echo ""
echo "📊 Check dashboard at http://localhost:3000"
echo "📈 Watch for changes in error rates and service health"

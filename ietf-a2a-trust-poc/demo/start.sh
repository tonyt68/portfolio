#!/bin/bash
# A2A Trust PoC Demo Startup Script

set -e

cd "$(dirname "$0")/.."

echo "Starting A2A Trust PoC Demo..."

# Check .env
if [ ! -f .env ]; then
    echo "ERROR: .env not found. Copy .env.example and fill in values."
    exit 1
fi

# Check certs
if [ ! -f certs/ca-root.crt ]; then
    echo "Certs not found. Generating..."
    python3 setup_keys.py
fi

# Start services
echo "Starting Docker Compose..."
docker compose up -d

echo ""
echo "Waiting for services (15s)..."
sleep 15

# Full startup smoke test
echo ""
echo "Running startup checks..."
python3 scripts/smoke_test.py
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Startup checks failed. Check output above."
    exit 1
fi

# Open browser
echo ""
if command -v open &>/dev/null; then
    open "http://localhost:8765"
elif command -v xdg-open &>/dev/null; then
    xdg-open "http://localhost:8765"
fi

echo "Demo ready at http://localhost:8765"
echo "Stop with: docker compose down"

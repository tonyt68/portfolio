#!/bin/bash
# Restart Docker Compose and verify all services + deps are ready

set -e

echo "Restarting A2A Trust PoC..."
docker compose down
docker compose up -d --build

echo ""
echo "Waiting for services to start (15s)..."
sleep 15

echo ""
echo "Running startup smoke tests..."
python3 scripts/smoke_test.py

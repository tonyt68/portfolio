#!/bin/bash

# A2A Trust PoC Demo Startup Script
# Starts Docker Compose + opens browser to demo

set -e

echo "🚀 Starting A2A Trust PoC Demo..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Copy .env.example to .env and fill in values."
    exit 1
fi

# Start Docker Compose
echo "📦 Starting Docker Compose (4 services)..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 5

# Health check
echo "🏥 Health checks..."
curl -s http://localhost:8001/health || echo "⚠️  MCP server not ready"
curl -s http://localhost:8002/health || echo "⚠️  Admin Bootstrap not ready"
curl -s http://localhost:8765/health || echo "⚠️  Demo web not ready"

# Open browser
echo "🌐 Opening browser to http://localhost:8765..."
if command -v open &> /dev/null; then
    open "http://localhost:8765"
elif command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:8765"
else
    echo "Visit http://localhost:8765 in your browser"
fi

echo ""
echo "✅ Demo started!"
echo ""
echo "Services:"
echo "  • Demo UI: http://localhost:8765"
echo "  • MCP Server: http://localhost:8001"
echo "  • Admin Bootstrap: http://localhost:8002"
echo "  • DynamoDB Local: http://localhost:8000"
echo ""
echo "To stop: docker-compose down"
echo ""

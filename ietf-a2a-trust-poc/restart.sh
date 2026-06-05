#!/bin/bash
# Restart Docker Compose and verify services

set -e

echo "🔄 Restarting A2A Trust PoC demo..."

# Stop containers
docker-compose down

# Start containers
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 5

# Check mcp_server is running
echo "🏥 Health check..."
docker-compose logs mcp_server | grep "Uvicorn running" && echo "✅ mcp_server running" || echo "❌ mcp_server failed"

# Show last 10 lines of logs
echo ""
echo "📋 Last logs:"
docker-compose logs mcp_server | tail -10

echo ""
echo "✅ Done! Demo available at http://localhost:8765"

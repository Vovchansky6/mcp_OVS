#!/bin/bash

# MCP Business AI Transformation - Startup Script

set -e

echo "🚀 Starting MCP Business AI Transformation Platform..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your API keys and configuration before running again."
    exit 1
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p logs
mkdir -p ssl
mkdir -p grafana/dashboards
mkdir -p grafana/datasources

# Build and start services
echo "🔨 Building Docker images..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 30

# Check service health
echo "🔍 Checking service health..."

# Check MCP Server
if curl -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "✅ MCP Server is healthy"
else
    echo "❌ MCP Server is not responding"
fi

# Check Frontend
if curl -f http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Frontend is healthy"
else
    echo "❌ Frontend is not responding"
fi

# Check Database
if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo "✅ PostgreSQL is healthy"
else
    echo "❌ PostgreSQL is not ready"
fi

# Check Redis
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is healthy"
else
    echo "❌ Redis is not ready"
fi

echo ""
echo "🎉 MCP Business AI Transformation Platform is starting up!"
echo ""
echo "📊 Access Points:"
echo "   • Frontend Dashboard:    http://localhost:3000"
echo "   • MCP Server API:        http://localhost:8000"
echo "   • API Documentation:    http://localhost:8000/docs"
echo "   • Grafana Dashboard:     http://localhost:3001 (admin/admin)"
echo "   • Prometheus:            http://localhost:9091"
echo "   • Jaeger Tracing:        http://localhost:16686"
echo ""
echo "📋 Useful Commands:"
echo "   • View logs:             docker-compose logs -f"
echo "   • Stop services:         docker-compose down"
echo "   • Restart services:      docker-compose restart"
echo "   • Check status:          docker-compose ps"
echo ""
echo "🔧 For development, run: npm run dev (frontend) and python -m uvicorn app.main:app --reload (backend)"
echo ""
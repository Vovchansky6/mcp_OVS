# MCP Business AI Transformation

Enterprise-grade MCP (Model Context Protocol) server with multi-agent system for business AI transformation.

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Agent Layer   │◄──►│   MCP Gateway    │◄──►│ Business APIs   │
│  (Orchestrator) │    │  (Protocol Hub)  │    │  (External)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   LLM Fabric    │    │ State Manager    │    │ Monitoring Hub  │
│ (Multi-Model)   │    │ (Redis+Postgres) │    │ (Observability) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚀 Features

### Core MCP Server
- **FastAPI-based** high-performance server
- **MCP Protocol** compliant (2024-11-05 spec)
- **Multi-provider LLM support** (Evolution Foundation Models, OpenAI, HuggingFace)
- **Circuit breaker** pattern for external API resilience
- **Rate limiting** with Redis-based sliding window
- **JWT & API Key** authentication
- **Prometheus metrics** and OpenTelemetry tracing

### Multi-Agent System
- **Specialized Agents**: Data Analyst, API Executor, Business Validator, Report Generator
- **Agent Registry** for dynamic agent management
- **Message Bus** for inter-agent communication
- **Task Orchestration** with intelligent agent selection
- **LangChain/LlamaIndex** integration for advanced AI capabilities

### Enterprise Features
- **Real-time Dashboard** with React + TypeScript
- **Business Domain Support**: Finance, Healthcare, Retail, Manufacturing, Technology
- **Observability Stack**: Prometheus, Grafana, Jaeger
- **Docker Compose** for easy deployment
- **Production-ready** with security best practices

## 🛠️ Technology Stack

### Frontend
- **Next.js 15** with App Router
- **TypeScript 5** for type safety
- **Tailwind CSS 4** with shadcn/ui components
- **Real-time updates** with WebSocket support

### Backend
- **Python 3.11** with FastAPI
- **PostgreSQL** for persistent storage
- **Redis** for caching and rate limiting
- **AsyncIO** for high concurrency

### AI/ML
- **Evolution Foundation Models** (Cloud.ru)
- **OpenAI API** compatibility
- **LangChain** for agent orchestration
- **LlamaIndex** for data indexing

### DevOps
- **Docker** containerization
- **Prometheus** monitoring
- **Grafana** dashboards
- **Jaeger** distributed tracing

## 📦 Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)

### Environment Configuration
Create a `.env` file:
```bash
# API Keys
EVOLUTION_API_KEY=your_evolution_api_key
OPENAI_API_KEY=your_openai_api_key
HUGGINGFACE_API_KEY=your_huggingface_api_key

# Security
SECRET_KEY=your-super-secret-key-change-in-production

# Database (optional, defaults work with Docker)
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/mcp_db
REDIS_URL=redis://localhost:6379
```

### Start the System
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Access Points
- **Frontend Dashboard**: http://localhost:3000
- **MCP Server API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Grafana Dashboard**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9091
- **Jaeger Tracing**: http://localhost:16686

## 🔧 Development

### Local Development Setup

#### Backend (MCP Server)
```bash
cd mcp_server
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Agent System
```bash
cd agent_system
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

#### Frontend
```bash
npm install
npm run dev
```

### Project Structure
```
├── src/                          # Next.js frontend
│   ├── app/                      # App Router pages
│   ├── components/               # React components
│   └── lib/                      # Utility functions
├── mcp_server/                   # FastAPI MCP server
│   ├── app/                      # Application code
│   │   ├── api/v1/              # API endpoints
│   │   ├── core/                # Core services
│   │   └── middleware/          # Custom middleware
│   └── tests/                   # Test suite
├── agent_system/                 # Multi-agent system
│   ├── core/                    # Agent framework
│   ├── agents/                  # Specialized agents
│   └── llm/                     # LLM providers
├── docker-compose.yml           # Multi-service deployment
└── docs/                        # Documentation
```

## 📊 API Usage

### MCP Protocol
The server implements the MCP protocol for tool and resource management:

```bash
# Initialize connection
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {}
    }
  }'

# List available tools
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
  }'

# Execute a tool
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "financial_analyzer",
      "arguments": {
        "data": {...}
      }
    }
  }'
```

### REST API
```bash
# Create a business task
curl -X POST http://localhost:8000/api/v1/resources/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "title": "Financial Analysis Q4",
    "description": "Analyze quarterly financial data",
    "domain": "finance",
    "priority": "high"
  }'

# Get system status
curl -X GET http://localhost:8000/api/v1/admin/system/status

# Health check
curl -X GET http://localhost:8000/api/v1/health
```

## 🔍 Monitoring & Observability

### Metrics
- **Request latency** and throughput
- **Agent performance** and task completion rates
- **LLM token usage** and costs
- **External API** success rates and circuit breaker status

### Tracing
- **Distributed tracing** with Jaeger
- **Request correlation** IDs
- **Agent communication** tracing

### Logging
- **Structured logging** with correlation IDs
- **Log levels**: DEBUG, INFO, WARNING, ERROR
- **JSON format** for easy parsing

## 🔒 Security

### Authentication
- **JWT tokens** for user authentication
- **API keys** for service-to-service communication
- **Rate limiting** per user/API key

### Authorization
- **Role-based access control** (RBAC)
- **Resource-level permissions**
- **CORS** configuration

### Data Protection
- **Input validation** and sanitization
- **SQL injection** prevention
- **XSS protection** headers

## 🚀 Deployment

### Production Deployment
```bash
# Set production environment variables
export NODE_ENV=production
export DEBUG=false

# Deploy with production configurations
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Cloud.ru Evolution AI Agents
The system is designed to deploy on Cloud.ru Evolution AI Agents platform:

1. **Container Registry**: Push Docker images to Cloud.ru registry
2. **AI Agent Configuration**: Configure agent endpoints and API keys
3. **Load Balancing**: Set up load balancer for high availability
4. **Monitoring**: Configure Cloud.ru monitoring integration

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Check the `/docs` directory
- **API Docs**: Visit http://localhost:8000/docs
- **Issues**: Create an issue on GitHub
- **Discussions**: Join our GitHub Discussions

## 🗺️ Roadmap

### Phase 1: Core Infrastructure ✅
- [x] MCP Server implementation
- [x] Multi-agent system
- [x] LLM provider integration
- [x] Basic monitoring

### Phase 2: Advanced Features (In Progress)
- [ ] Advanced agent orchestration
- [ ] Custom tool development framework
- [ ] Advanced analytics and reporting
- [ ] Multi-tenancy support

### Phase 3: Enterprise Features (Planned)
- [ ] Advanced security features
- [ ] Compliance certifications
- [ ] Advanced monitoring and alerting
- [ ] Performance optimization

### Phase 4: AI/ML Enhancements (Future)
- [ ] Custom model training
- [ ] Advanced prompt engineering
- [ ] Multi-modal AI capabilities
- [ ] AutoML integration

---

Built with ❤️ for enterprise AI transformation
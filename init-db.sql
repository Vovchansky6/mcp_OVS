-- MCP Business AI Transformation - Database Initialization
-- PostgreSQL 15+

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS mcp;
CREATE SCHEMA IF NOT EXISTS agents;
CREATE SCHEMA IF NOT EXISTS analytics;

-- Set search path
SET search_path TO mcp, agents, analytics, public;

-- =============================================================================
-- MCP Schema - Core MCP Protocol Tables
-- =============================================================================

-- Tools registry
CREATE TABLE IF NOT EXISTS mcp.tools (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    input_schema JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'active',
    category VARCHAR(100),
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Resources registry
CREATE TABLE IF NOT EXISTS mcp.resources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uri VARCHAR(500) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    mime_type VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tool executions log
CREATE TABLE IF NOT EXISTS mcp.tool_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tool_name VARCHAR(255) NOT NULL,
    agent_id UUID,
    task_id UUID,
    parameters JSONB NOT NULL DEFAULT '{}',
    result JSONB,
    error TEXT,
    execution_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- Agents Schema - Multi-Agent System Tables
-- =============================================================================

-- Agents registry
CREATE TABLE IF NOT EXISTS agents.agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    type VARCHAR(100) NOT NULL,
    description TEXT,
    capabilities TEXT[] DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'idle',
    current_task_id UUID,
    tasks_completed INTEGER DEFAULT 0,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Business tasks
CREATE TABLE IF NOT EXISTS agents.tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    domain VARCHAR(100) NOT NULL,
    priority VARCHAR(50) DEFAULT 'medium',
    status VARCHAR(50) DEFAULT 'pending',
    agent_id UUID REFERENCES agents.agents(id),
    input_data JSONB DEFAULT '{}',
    output_data JSONB,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Agent messages (for inter-agent communication)
CREATE TABLE IF NOT EXISTS agents.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sender_id UUID NOT NULL,
    recipient_id UUID NOT NULL,
    message_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    correlation_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Business rules
CREATE TABLE IF NOT EXISTS agents.business_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    domain VARCHAR(100) NOT NULL,
    condition TEXT NOT NULL,
    action TEXT NOT NULL,
    priority INTEGER DEFAULT 1,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- Analytics Schema - Monitoring and Analytics Tables
-- =============================================================================

-- LLM usage tracking
CREATE TABLE IF NOT EXISTS analytics.llm_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    cost DECIMAL(10, 6) DEFAULT 0,
    agent_id UUID,
    task_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- API calls tracking
CREATE TABLE IF NOT EXISTS analytics.api_calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_name VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    url TEXT NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    success BOOLEAN DEFAULT false,
    error TEXT,
    agent_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- System metrics (time-series like)
CREATE TABLE IF NOT EXISTS analytics.metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(255) NOT NULL,
    metric_value DECIMAL(15, 4) NOT NULL,
    labels JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Business analysis results
CREATE TABLE IF NOT EXISTS analytics.business_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain VARCHAR(100) NOT NULL,
    analysis_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'processing',
    data_sources TEXT[] DEFAULT '{}',
    parameters JSONB DEFAULT '{}',
    results JSONB,
    insights TEXT[] DEFAULT '{}',
    recommendations TEXT[] DEFAULT '{}',
    confidence_score DECIMAL(5, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- =============================================================================
-- Indexes for Performance
-- =============================================================================

-- Tools indexes
CREATE INDEX IF NOT EXISTS idx_tools_status ON mcp.tools(status);
CREATE INDEX IF NOT EXISTS idx_tools_category ON mcp.tools(category);
CREATE INDEX IF NOT EXISTS idx_tools_tags ON mcp.tools USING GIN(tags);

-- Tool executions indexes
CREATE INDEX IF NOT EXISTS idx_tool_executions_tool_name ON mcp.tool_executions(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_executions_created_at ON mcp.tool_executions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_executions_agent_id ON mcp.tool_executions(agent_id);

-- Agents indexes
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents.agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_type ON agents.agents(type);
CREATE INDEX IF NOT EXISTS idx_agents_capabilities ON agents.agents USING GIN(capabilities);

-- Tasks indexes
CREATE INDEX IF NOT EXISTS idx_tasks_status ON agents.tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_domain ON agents.tasks(domain);
CREATE INDEX IF NOT EXISTS idx_tasks_agent_id ON agents.tasks(agent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON agents.tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON agents.tasks(priority);

-- Messages indexes
CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON agents.messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_recipient_id ON agents.messages(recipient_id);
CREATE INDEX IF NOT EXISTS idx_messages_correlation_id ON agents.messages(correlation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON agents.messages(created_at DESC);

-- Analytics indexes
CREATE INDEX IF NOT EXISTS idx_llm_usage_provider ON analytics.llm_usage(provider);
CREATE INDEX IF NOT EXISTS idx_llm_usage_created_at ON analytics.llm_usage(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_calls_api_name ON analytics.api_calls(api_name);
CREATE INDEX IF NOT EXISTS idx_api_calls_created_at ON analytics.api_calls(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_name_created ON analytics.metrics(metric_name, created_at DESC);

-- =============================================================================
-- Triggers for updated_at
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
DO $$
DECLARE
    tables TEXT[] := ARRAY[
        'mcp.tools',
        'mcp.resources',
        'agents.agents',
        'agents.business_rules'
    ];
    t TEXT;
BEGIN
    FOREACH t IN ARRAY tables
    LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS update_%s_updated_at ON %s;
            CREATE TRIGGER update_%s_updated_at
                BEFORE UPDATE ON %s
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        ', replace(t, '.', '_'), t, replace(t, '.', '_'), t);
    END LOOP;
END;
$$;

-- =============================================================================
-- Initial Data - Default Tools
-- =============================================================================

INSERT INTO mcp.tools (name, description, input_schema, category, tags) VALUES
('financial_analyzer', 'Analyze financial data and generate insights', 
 '{"type": "object", "properties": {"data": {"type": "object"}, "analysis_type": {"type": "string"}}, "required": ["data"]}',
 'analytics', ARRAY['finance', 'analysis', 'reporting']),
 
('api_connector', 'Connect to external business APIs',
 '{"type": "object", "properties": {"url": {"type": "string"}, "method": {"type": "string"}, "headers": {"type": "object"}}, "required": ["url"]}',
 'integration', ARRAY['api', 'external', 'connector']),
 
('data_validator', 'Validate business rules and compliance',
 '{"type": "object", "properties": {"data": {"type": "object"}, "rules": {"type": "array"}}, "required": ["data", "rules"]}',
 'validation', ARRAY['validation', 'compliance', 'rules']),
 
('report_generator', 'Generate automated business reports',
 '{"type": "object", "properties": {"template": {"type": "string"}, "data": {"type": "object"}, "format": {"type": "string"}}, "required": ["data"]}',
 'reporting', ARRAY['report', 'document', 'generation']),
 
('database_query', 'Execute database queries and analysis',
 '{"type": "object", "properties": {"query": {"type": "string"}, "parameters": {"type": "object"}}, "required": ["query"]}',
 'data', ARRAY['database', 'sql', 'query']),
 
('llm_processor', 'Process natural language requests',
 '{"type": "object", "properties": {"prompt": {"type": "string"}, "max_tokens": {"type": "integer"}, "temperature": {"type": "number"}}, "required": ["prompt"]}',
 'ai', ARRAY['llm', 'nlp', 'ai'])
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- Initial Data - Default Agents
-- =============================================================================

INSERT INTO agents.agents (name, type, description, capabilities, config) VALUES
('Data Analyst', 'data_analyst', 'Specialized agent for data analysis and insights generation',
 ARRAY['financial_analysis', 'data_processing', 'report_generation', 'data_visualization'],
 '{"max_concurrent_tasks": 3, "specialization": "analytics"}'),
 
('API Executor', 'api_executor', 'Specialized agent for executing external API calls',
 ARRAY['api_calls', 'data_retrieval', 'webhook_execution', 'api_monitoring', 'rate_limiting', 'error_handling'],
 '{"max_concurrent_tasks": 5, "specialization": "integration"}'),
 
('Business Validator', 'business_validator', 'Specialized agent for business rule validation and compliance',
 ARRAY['data_validation', 'compliance_check', 'rule_execution', 'audit_logging'],
 '{"max_concurrent_tasks": 3, "specialization": "compliance"}'),
 
('Report Generator', 'report_generator', 'Specialized agent for generating business reports and documents',
 ARRAY['report_generation', 'document_creation', 'data_visualization', 'template_processing'],
 '{"max_concurrent_tasks": 2, "specialization": "reporting"}')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Grant Permissions
-- =============================================================================

-- Create application user if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'mcp_app') THEN
        CREATE ROLE mcp_app WITH LOGIN PASSWORD 'mcp_app_password';
    END IF;
END
$$;

-- Grant permissions
GRANT USAGE ON SCHEMA mcp, agents, analytics TO mcp_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA mcp, agents, analytics TO mcp_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA mcp, agents, analytics TO mcp_app;

-- Default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA mcp GRANT ALL ON TABLES TO mcp_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA agents GRANT ALL ON TABLES TO mcp_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT ALL ON TABLES TO mcp_app;

-- =============================================================================
-- Verification
-- =============================================================================

DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables 
    WHERE table_schema IN ('mcp', 'agents', 'analytics');
    
    RAISE NOTICE 'Database initialization complete. Created % tables.', table_count;
END;
$$;

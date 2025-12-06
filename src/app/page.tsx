"use client"

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { 
  Brain, 
  Network, 
  BarChart3, 
  Settings, 
  Activity, 
  Database,
  Globe,
  Shield,
  Zap,
  CheckCircle,
  AlertCircle,
  Clock,
  Users,
  TrendingUp,
  FileText,
  MessageSquare,
  Cpu
} from 'lucide-react'

interface AgentStatus {
  id: string
  name: string
  status: 'active' | 'idle' | 'processing' | 'error'
  lastActivity: string
  tasksCompleted: number
}

interface MCPServerStatus {
  status: 'online' | 'offline' | 'degraded'
  uptime: number
  activeConnections: number
  toolsAvailable: number
  requestsPerSecond: number
}

interface Task {
  id: string
  title: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  agent: string
  startTime: string
  description: string
}

export default function Home() {
  const [serverStatus, setServerStatus] = useState<MCPServerStatus>({
    status: 'offline',
    uptime: 0,
    activeConnections: 0,
    toolsAvailable: 0,
    requestsPerSecond: 0
  })

  const [agents, setAgents] = useState<AgentStatus[]>([
    { id: '1', name: 'Data Analyst', status: 'idle', lastActivity: '2 min ago', tasksCompleted: 45 },
    { id: '2', name: 'API Executor', status: 'active', lastActivity: 'now', tasksCompleted: 128 },
    { id: '3', name: 'Business Validator', status: 'idle', lastActivity: '5 min ago', tasksCompleted: 67 },
    { id: '4', name: 'Report Generator', status: 'processing', lastActivity: '1 min ago', tasksCompleted: 23 }
  ])

  const [tasks, setTasks] = useState<Task[]>([
    { id: '1', title: 'Financial Analysis Q4', status: 'completed', progress: 100, agent: 'Data Analyst', startTime: '10:30 AM', description: 'Analyze quarterly financial data and generate insights' },
    { id: '2', title: 'API Integration Test', status: 'processing', progress: 65, agent: 'API Executor', startTime: '11:15 AM', description: 'Test external API connectivity and data flow' },
    { id: '3', title: 'Compliance Check', status: 'pending', progress: 0, agent: 'Business Validator', startTime: 'Pending', description: 'Validate business rules and compliance requirements' }
  ])

  const [newTask, setNewTask] = useState({ title: '', description: '' })
  const [logs, setLogs] = useState<string[]>([
    '[10:30:45] MCP Server started successfully',
    '[10:31:02] Agent "Data Analyst" connected',
    '[10:31:15] Tool "financial_analyzer" registered',
    '[10:32:01] Task "Financial Analysis Q4" initiated',
    '[10:35:22] Task "Financial Analysis Q4" completed successfully'
  ])

  useEffect(() => {
    // Simulate real-time updates
    const interval = setInterval(() => {
      setServerStatus(prev => ({
        ...prev,
        uptime: prev.uptime + 1,
        requestsPerSecond: Math.floor(Math.random() * 50) + 10,
        activeConnections: Math.floor(Math.random() * 20) + 5
      }))

      // Randomly update agent statuses
      if (Math.random() > 0.8) {
        setAgents(prev => prev.map(agent => {
          if (Math.random() > 0.7) {
            const statuses: AgentStatus['status'][] = ['active', 'idle', 'processing']
            return { ...agent, status: statuses[Math.floor(Math.random() * statuses.length)] }
          }
          return agent
        }))
      }

      // Update task progress
      setTasks(prev => prev.map(task => {
        if (task.status === 'processing' && task.progress < 100) {
          const newProgress = Math.min(task.progress + Math.floor(Math.random() * 15) + 5, 100)
          return { 
            ...task, 
            progress: newProgress,
            status: newProgress === 100 ? 'completed' : 'processing'
          }
        }
        return task
      }))
    }, 2000)

    return () => clearInterval(interval)
  }, [])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
      case 'completed':
      case 'online':
        return 'text-green-600 bg-green-50'
      case 'processing':
      case 'degraded':
        return 'text-yellow-600 bg-yellow-50'
      case 'error':
      case 'failed':
      case 'offline':
        return 'text-red-600 bg-red-50'
      default:
        return 'text-gray-600 bg-gray-50'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
      case 'completed':
      case 'online':
        return <CheckCircle className="w-4 h-4" />
      case 'processing':
      case 'degraded':
        return <Clock className="w-4 h-4" />
      case 'error':
      case 'failed':
      case 'offline':
        return <AlertCircle className="w-4 h-4" />
      default:
        return <Clock className="w-4 h-4" />
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
              <Brain className="w-8 h-8 text-blue-600" />
              MCP Business AI Transformation
            </h1>
            <p className="text-slate-600 mt-2">Enterprise-grade multi-agent system for business process automation</p>
          </div>
          <div className="flex items-center gap-4">
            <Badge className={`flex items-center gap-2 ${getStatusColor(serverStatus.status)}`}>
              {getStatusIcon(serverStatus.status)}
              Server {serverStatus.status}
            </Badge>
            <Button variant="outline" size="sm">
              <Settings className="w-4 h-4 mr-2" />
              Settings
            </Button>
          </div>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-600">Active Agents</p>
                  <p className="text-2xl font-bold text-slate-900">{agents.filter(a => a.status === 'active').length}</p>
                </div>
                <Users className="w-8 h-8 text-blue-600 opacity-50" />
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-600">Tasks Completed</p>
                  <p className="text-2xl font-bold text-slate-900">{agents.reduce((sum, a) => sum + a.tasksCompleted, 0)}</p>
                </div>
                <CheckCircle className="w-8 h-8 text-green-600 opacity-50" />
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-600">Requests/sec</p>
                  <p className="text-2xl font-bold text-slate-900">{serverStatus.requestsPerSecond}</p>
                </div>
                <Activity className="w-8 h-8 text-purple-600 opacity-50" />
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-600">Uptime</p>
                  <p className="text-2xl font-bold text-slate-900">{Math.floor(serverStatus.uptime / 60)}m</p>
                </div>
                <Zap className="w-8 h-8 text-yellow-600 opacity-50" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="agents">Agents</TabsTrigger>
            <TabsTrigger value="tasks">Tasks</TabsTrigger>
            <TabsTrigger value="mcp-tools">MCP Tools</TabsTrigger>
            <TabsTrigger value="monitoring">Monitoring</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5" />
                    System Performance
                  </CardTitle>
                  <CardDescription>Real-time system metrics and performance indicators</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>CPU Usage</span>
                      <span>42%</span>
                    </div>
                    <Progress value={42} />
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Memory Usage</span>
                      <span>68%</span>
                    </div>
                    <Progress value={68} />
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>API Rate Limit</span>
                      <span>23%</span>
                    </div>
                    <Progress value={23} />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <MessageSquare className="w-5 h-5" />
                    Recent Activity
                  </CardTitle>
                  <CardDescription>Latest system events and agent activities</CardDescription>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-48">
                    <div className="space-y-2">
                      {logs.map((log, index) => (
                        <div key={index} className="text-sm font-mono text-slate-600">
                          {log}
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="agents" className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {agents.map((agent) => (
                <Card key={agent.id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">{agent.name}</CardTitle>
                      <Badge className={`flex items-center gap-1 ${getStatusColor(agent.status)}`}>
                        {getStatusIcon(agent.status)}
                        {agent.status}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-slate-600">Last Activity:</span>
                        <span>{agent.lastActivity}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-slate-600">Tasks Completed:</span>
                        <span className="font-medium">{agent.tasksCompleted}</span>
                      </div>
                      <Separator />
                      <div className="flex gap-2 pt-2">
                        <Button size="sm" variant="outline" className="flex-1">
                          Configure
                        </Button>
                        <Button size="sm" className="flex-1">
                          View Details
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="tasks" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="w-5 h-5" />
                  Task Management
                </CardTitle>
                <CardDescription>Create and monitor agent tasks</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Task Title</label>
                    <Input 
                      placeholder="Enter task title..."
                      value={newTask.title}
                      onChange={(e) => setNewTask({...newTask, title: e.target.value})}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Agent</label>
                    <select className="w-full p-2 border rounded-md">
                      {agents.map(agent => (
                        <option key={agent.id} value={agent.id}>{agent.name}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Description</label>
                  <Textarea 
                    placeholder="Describe the task..."
                    value={newTask.description}
                    onChange={(e) => setNewTask({...newTask, description: e.target.value})}
                  />
                </div>
                <Button className="w-full">
                  Create Task
                </Button>
              </CardContent>
            </Card>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {tasks.map((task) => (
                <Card key={task.id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">{task.title}</CardTitle>
                      <Badge className={getStatusColor(task.status)}>
                        {getStatusIcon(task.status)}
                        {task.status}
                      </Badge>
                    </div>
                    <CardDescription>{task.description}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div className="flex justify-between text-sm">
                        <span className="text-slate-600">Agent:</span>
                        <span>{task.agent}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-slate-600">Start Time:</span>
                        <span>{task.startTime}</span>
                      </div>
                      <div className="space-y-1">
                        <div className="flex justify-between text-sm">
                          <span>Progress:</span>
                          <span>{task.progress}%</span>
                        </div>
                        <Progress value={task.progress} />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="mcp-tools" className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[
                { name: 'Financial Analyzer', description: 'Analyze financial data and generate insights', icon: BarChart3 },
                { name: 'API Connector', description: 'Connect to external business APIs', icon: Globe },
                { name: 'Data Validator', description: 'Validate business rules and compliance', icon: Shield },
                { name: 'Report Generator', description: 'Generate automated business reports', icon: FileText },
                { name: 'Database Query', description: 'Execute database queries and analysis', icon: Database },
                { name: 'LLM Processor', description: 'Process natural language requests', icon: Brain }
              ].map((tool, index) => (
                <Card key={index}>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <tool.icon className="w-5 h-5 text-blue-600" />
                      {tool.name}
                    </CardTitle>
                    <CardDescription>{tool.description}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" className="flex-1">
                        Test
                      </Button>
                      <Button size="sm" className="flex-1">
                        Configure
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="monitoring" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Activity className="w-5 h-5" />
                    System Health
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <Alert>
                      <CheckCircle className="h-4 w-4" />
                      <AlertDescription>
                        All systems operational. No critical issues detected.
                      </AlertDescription>
                    </Alert>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="text-center p-4 bg-green-50 rounded-lg">
                        <p className="text-2xl font-bold text-green-600">99.9%</p>
                        <p className="text-sm text-slate-600">Uptime</p>
                      </div>
                      <div className="text-center p-4 bg-blue-50 rounded-lg">
                        <p className="text-2xl font-bold text-blue-600">124ms</p>
                        <p className="text-sm text-slate-600">Avg Response</p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Cpu className="w-5 h-5" />
                    Resource Usage
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>LLM Tokens Used</span>
                        <span>45,234 / 100,000</span>
                      </div>
                      <Progress value={45} />
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>API Calls Today</span>
                        <span>892 / 5,000</span>
                      </div>
                      <Progress value={18} />
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Storage Used</span>
                        <span>2.3 GB / 10 GB</span>
                      </div>
                      <Progress value={23} />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
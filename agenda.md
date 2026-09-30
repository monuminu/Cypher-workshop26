# Building Intelligent Agents — Tools, Orchestration & Governance

### Cypher 2026 · Sample One-Day Workshop Agenda

> **Planning note:** This is a sample teaching schedule, not a confirmed Cypher event timetable.
>
> **Audience:** Software Developers
> **Format:** Lecture + Hands-on Labs
> **Duration:** Full Day (9:00 AM - 5:00 PM)
> **Prerequisites:** Azure subscription, basic Python experience, VS Code installed

---

## Schedule at a Glance

| Time | Session | Format |
|:---|:---|:---:|
| 9:00 - 9:30 | Welcome & Introduction to AI Agents | Lecture |
| 9:30 - 10:30 | Lab 1 - Build Your First Agent with Azure AI Foundry| Hands-on |
| 10:30 - 10:45 | Break | - |
| 10:45 - 11:45 | Lab 2 - Tools, MCP Servers & Foundry IQ | Lecture + Hands-on |
| 11:45 - 12:30 | Lunch | - |
| 12:30 - 1:15 | Microsoft Agent Framework Deep Dive | Lecture |
| 1:15 - 2:15 | Lab 3 - Build Agents with Microsoft Agent Framework | Hands-on |
| 2:15 - 2:30 | Break | - |
| 2:30 - 3:15 | Multi-Agent Orchestration — Workflows, A2A & Connected Agents | Lecture |
| 3:15 - 4:15 | Lab 4 - Multi-Agent Workflows & A2A Integration | Hands-on |
| 4:15 - 5:00 | Production Best Practices & Wrap-up | Lecture + Q&A |

---

## Pre-Workshop Setup

Participants should complete the following before the workshop:

- [ ] **Azure subscription** - [Create a free account](https://azure.microsoft.com/free/) if needed
- [ ] **Python 3.10+** installed - [Download](https://www.python.org/downloads/)
- [ ] **VS Code** with the Python extension - [Download](https://code.visualstudio.com/)
- [ ] **Azure CLI** installed and signed in (`az login`) - [Install](https://learn.microsoft.com/cli/azure/install-azure-cli)
- [ ] **Azure Developer CLI (azd)** installed - [Install](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- [ ] **Docker Desktop** installed (for hosted agent lab) - [Download](https://www.docker.com/products/docker-desktop/)
- [ ] **Node.js 18+** installed (for MCP server lab) - [Download](https://nodejs.org/)

---

## Session Details

---

### 9:00 - 9:30 | Welcome & Introduction to AI Agents on Azure

**Format:** Lecture (30 min)

#### Topics

- **What are AI Agents?**
  - From chatbots to autonomous agents — the evolution
  - Key characteristics: reasoning, tool use, memory, planning
  - Agent design patterns: ReAct, tool-augmented generation, multi-agent

- **The Azure AI Agent Platform**
  - Azure AI Foundry — portal, projects, and resource model
  - Model catalog — GPT-4o, Llama, DeepSeek, Cohere, and more
  - Two pillars for building agents:

    | Pillar | What It Is | Best For |
    |:---|:---|:---|
    | **Foundry Agent Service** | Managed runtime for prompt & hosted agents | Rapid agent development, no-code/low-code, enterprise hosting |
    | **Microsoft Agent Framework** | Open-source SDK (successor to Semantic Kernel + AutoGen) | Code-first control, graph-based workflows, multi-framework agents |

- **Key Protocols & Standards**
  - **MCP (Model Context Protocol)** — open standard for tool integration
  - **A2A (Agent-to-Agent)** — standardized inter-agent communication
  - How MCP and A2A fit into the Azure AI ecosystem

#### Key Takeaways

> Participants understand the two-pillar architecture (Foundry Agent Service + Agent Framework), the role of MCP and A2A protocols, and can identify which approach fits their scenario.

---

### 9:30 - 10:30 | Lab 1 - Build Your First Agent with Foundry Agent Service

**Format:** Hands-on Lab (60 min)

#### Objectives

- Set up the development environment
- Create an Azure AI Foundry project
- Build and run a prompt agent using the Python SDK
- Interact with the agent through threads and conversations

---

### 10:30 - 10:45 | Break (15 min)

---

### 10:45 - 11:45 | Lab 2 - Tools, MCP Servers & Foundry IQ

**Format:** Lecture (20 min) + Hands-on Lab (40 min)

#### Lecture: The Agent Tool Ecosystem

- **Built-in Tools Overview**

  | Tool | What It Does |
  |:---|:---|
  | Code Interpreter | Execute Python code, generate charts, process files |
  | File Search | Search and retrieve from uploaded documents |
  | Bing Grounding | Access real-time web information via Bing Search |
  | Azure Functions | Call serverless functions as agent tools |
  | OpenAPI | Connect to any REST API via OpenAPI spec |
  | MCP Servers | Connect to any Model Context Protocol tool server |
  | Memory | Persistent long-term memory across sessions (preview) |

- **Model Context Protocol (MCP) — Deep Dive**
  - What is MCP? Open standard for tool integration with LLMs
  - MCP in Foundry Agent Service: connect remote MCP servers as tools
  - MCP tool catalog: Azure DevOps, GitHub, and custom servers
  - Authentication, approval workflows, and security best practices
  - Exposing your own services as MCP servers via Azure Functions

- **Foundry IQ — Enterprise Knowledge Layer**
  - What is Foundry IQ? Managed knowledge layer for enterprise data
  - Knowledge bases and knowledge sources (Azure, SharePoint, OneLake, Web)
  - Agentic retrieval engine — multi-query, iterative search with reasoning
  - Connecting Foundry IQ knowledge bases to agents
  - Foundry IQ vs. File Search vs. Azure AI Search — when to use which

    | Approach | Best For |
    |:---|:---|
    | **Foundry IQ** | Multi-source enterprise knowledge with agentic retrieval |
    | **File Search** | User-uploaded documents during an interaction |
    | **Azure AI Search** | Custom vector/hybrid search with full index control |
    | **Memory** | User-specific context that persists over time |

- **Function Calling** — Define custom functions the agent can invoke
- **Tool selection best practices** — When to use which tool

#### Lab Steps

1. **Code Interpreter & File Search** (10 min)
   - Attach Code Interpreter to your agent for data analysis
   - Upload documents and query them with File Search

2. **Connect an MCP Server** (15 min)
   - Connect the GitHub MCP server to your agent
   - Configure `server_label`, `server_url`, and authentication headers
   - Ask the agent to query GitHub repositories
   - Review MCP tool call approval and auditing

3. **Foundry IQ Knowledge Base** (10 min)
   - Create a Foundry IQ knowledge base in the portal
   - Connect knowledge sources (sample documents)
   - Attach the knowledge base to your agent
   - Test agentic retrieval with citation-backed answers

4. **Bing Grounding + Custom Functions** (5 min)
   - Create an agent with Bing Grounding for real-time web search
   - Define and attach a custom function

---

### 11:45 - 12:30 | Lunch (45 min)

---

### 12:30 - 1:15 | Microsoft Agent Framework Deep Dive

**Format:** Lecture (45 min)

#### Topics

- **What is Microsoft Agent Framework?**
  - Open-source SDK — successor to Semantic Kernel + AutoGen
  - Two core capabilities: **Agents** and **Workflows**
  - Supported model providers: Azure OpenAI, OpenAI, Anthropic, Ollama, and more
  - Python and C# support

- **Agent Framework Architecture**

  | Component | Description |
  |:---|:---|
  | **Agents** | Individual agents with LLM, tools, MCP servers, and middleware |
  | **Workflows** | Graph-based orchestration with type-safe routing and checkpointing |
  | **Model Clients** | Chat completions and Responses API clients |
  | **Session** | State management for conversations and context |
  | **Context Providers** | Agent memory and contextual data injection |
  | **Middleware** | Intercept and transform agent actions (human-in-the-loop, logging) |

- **Tools & MCP in Agent Framework**
  - Native tool functions
  - MCP integration types:
    - `MCPStdioTool` — local MCP servers via stdin/stdout
    - `MCPStreamableHTTPTool` — remote HTTP/SSE MCP servers
    - `MCPWebsocketTool` — WebSocket MCP servers
  - Exposing agents _as_ MCP servers with `.as_mcp_server()`

- **A2A Protocol in Agent Framework**
  - `A2AAgent` — wrap any remote A2A-compliant endpoint
  - Streaming responses via Server-Sent Events
  - Long-running tasks with `background=True` and continuation tokens
  - Authentication with `AuthInterceptor`

- **Hosting Options**

  | Option | Best For |
  |:---|:---|
  | A2A Protocol | Multi-agent systems, cross-framework interop |
  | OpenAI-Compatible Endpoints | Chat Completions / Responses API clients |
  | Azure Functions (Durable) | Serverless, long-running tasks |
  | AG-UI Protocol | Web-based AI agent frontends |

- **Agent Framework vs. Foundry Agent Service — Choosing the Right Approach**

  | Criteria | Foundry Agent Service | Agent Framework |
  |:---|:---|:---|
  | Orchestration | Managed, declarative | Code-first, graph-based |
  | Control | System prompt-driven | Full programmatic control |
  | Compute | Managed by Foundry | You manage (Container Apps, Functions, etc.) |
  | Workflows | Visual builder + YAML | Python/C# code with type safety |
  | Best for | Rapid prototyping, enterprise hosting | Custom logic, multi-framework agents |

#### Key Takeaways

> Participants understand the Agent Framework architecture, how MCP and A2A protocols are used in code-first agents, and can choose between Foundry Agent Service and Agent Framework for their use case.

---

### 1:15 - 2:15 | Lab 3 - Build Agents with Microsoft Agent Framework

**Format:** Hands-on Lab (60 min)

#### Objectives

- Build an agent using the Microsoft Agent Framework SDK
- Integrate MCP tools (local and remote)
- Connect to a remote A2A agent
- Compare the Agent Framework experience with Foundry Agent Service

---

### 2:15 - 2:30 | Break (15 min)

---

### 2:30 - 3:15 | Multi-Agent Orchestration — Workflows, A2A & Connected Agents

**Format:** Lecture (45 min)

#### Topics

- **Why Multi-Agent?**
  - Single agent limitations
  - Specialization, delegation, and collaboration patterns
  - When to use multi-agent vs. a single agent with many tools

- **Foundry Workflows — Visual Multi-Agent Orchestration**
  - What are workflows? Declarative, UI-based agent orchestration
  - Workflow patterns:

    | Pattern | Description | Use Case |
    |:---|:---|:---|
    | **Sequential** | Passes results from one agent to the next in order | Step-by-step pipelines, multi-stage processing |
    | **Group Chat** | Dynamically passes control between agents | Escalation, expert handoff, dynamic collaboration |
    | **Human in the Loop** | Asks the user a question and awaits input | Approval requests, clarifying questions |

  - Creating workflows in the Foundry portal
  - Workflow YAML editing in VS Code
  - Workflow versioning, change logs, and visual monitoring

- **Agent Framework Workflows — Code-First Orchestration**
  - Graph-based workflow architecture
  - Key features: type safety, conditional routing, parallel processing, checkpointing
  - Orchestration patterns: sequential, concurrent, hand-off, magentic
  - Human-in-the-loop with request/response patterns
  - Comparing Foundry Workflows vs. Agent Framework Workflows

    | Aspect | Foundry Workflows | Agent Framework Workflows |
    |:---|:---|:---|
    | Interface | Visual builder + YAML | Python / C# code |
    | Routing | Template-based patterns | Graph-based with custom logic |
    | Checkpointing | Managed | Developer-controlled |
    | Best for | No-code/low-code teams | Full control, complex branching |

- **Connected Agents in Foundry**
  - Architecture: main agent + connected agents
  - How connected agents communicate and aggregate responses
  - The `ConnectedAgentTool` API

- **A2A Protocol for Cross-System Agent Communication**
  - A2A protocol specification: agent cards, message-based communication, tasks
  - A2A in Foundry Agent Service — connecting external agent endpoints
  - A2A in Agent Framework — `A2AAgent` for cross-framework interop
  - A2A vs. Connected Agents — choosing the right approach

    | Criteria | Connected Agents | A2A Protocol |
    |:---|:---|:---|
    | Scope | Within Foundry project | Cross-platform, cross-framework |
    | Protocol | Foundry-native | Open standard (a2a-protocol.org) |
    | Discovery | By agent ID | Via agent cards |
    | Best for | Internal agent teams | External / multi-vendor integration |

- **Hosted Agents**
  - Containerized agents with Agent Framework or LangGraph
  - Docker + Azure Developer CLI (`azd`) deployment
  - When to choose hosted agents vs. prompt agents

#### Key Takeaways

> Participants can design multi-agent architectures using Foundry Workflows, Agent Framework Workflows, Connected Agents, and A2A. They understand when to use each orchestration approach and how the protocols enable interoperability.

---

### 3:15 - 4:15 | Lab 4 - Multi-Agent Workflows & A2A Integration

**Format:** Hands-on Lab (60 min)

#### Objectives

- Build a Foundry Workflow with multiple agents (visual orchestration)
- Build a code-first workflow with Microsoft Agent Framework
- Connect agents across systems using the A2A protocol

#### Lab Steps

1. **Foundry Workflow — Sequential Pipeline** (15 min)
   - Open the Foundry portal and create a new **Sequential** workflow
   - Add two agent nodes:
     - **Research Agent** — uses Bing Grounding to gather information
     - **Writer Agent** — synthesizes findings into a summary
   - Connect the nodes, save, and run the workflow
   - Verify each node completes and review the output

2. **Foundry Workflow — Human in the Loop** (10 min)
   - Add a **Human in the Loop** node between the agents
   - Configure an approval step: "Review research findings before writing"
   - Run the workflow and approve/reject at the human step
   - Observe how the workflow pauses and resumes

3. **Agent Framework Workflow — Code-First** (20 min)
   - Build a graph-based workflow with Agent Framework:
     - Define a `StateGraph` with typed state
     - Create executor nodes for specialized agents
     - Add conditional edges for routing
     - Enable checkpointing for recovery
   - Run the workflow and observe agent collaboration
   - Compare the code-first experience vs. the Foundry visual builder

4. **A2A Cross-System Integration** (15 min)
   - Expose an Agent Framework agent as an A2A endpoint
   - Connect the A2A endpoint to a Foundry agent using the A2A tool
   - Send a query that requires both agents to collaborate
   - Observe the cross-system communication flow
   - Review agent cards and message exchange

---

### 4:15 - 5:00 | Production Best Practices & Wrap-up

**Format:** Lecture + Q&A (45 min)

#### Topics

- **Observability & Monitoring**
  - End-to-end tracing with Application Insights
  - Monitoring agent decisions, tool calls, and token usage
  - Agent Framework telemetry and middleware-based logging
  - Setting up alerts for failures and performance degradation

- **Security & Identity**
  - Microsoft Entra authentication and RBAC
  - Content filters and safety guardrails
  - MCP security best practices: allow-lists, approval workflows, auditing
  - A2A authentication with `AuthInterceptor`
  - Virtual network isolation and data protection
  - Managed credentials and On-Behalf-Of (OBO) authentication

- **Deployment & Scaling**
  - Agent versioning and stable endpoints
  - Hosted agents: Docker + `azd` deployment to Foundry
  - Agent Framework hosting: Azure Functions (Durable), Container Apps
  - Publishing to Microsoft Teams and Microsoft 365 Copilot
  - Entra Agent Registry for enterprise discovery

- **Foundry IQ in Production**
  - Connecting multiple knowledge sources at scale
  - Permission-aware retrieval and data governance
  - Foundry IQ vs. Fabric IQ vs. Work IQ — choosing the right IQ layer

    | IQ Layer | Data Domain | Use Case |
    |:---|:---|:---|
    | **Foundry IQ** | Enterprise data (Azure, SharePoint, OneLake, Web) | Agent knowledge grounding |
    | **Fabric IQ** | Business analytics (OneLake, Power BI) | Data reasoning and analytics |
    | **Work IQ** | Collaboration signals (M365 docs, meetings, chats) | Organizational context |

- **Cost Management**
  - Understanding token consumption and tool call costs
  - MCP tool call billing and Bing transaction costs
  - Optimizing agent instructions for efficiency
  - Monitoring usage with Azure Cost Management

- **Choosing Your Architecture**

  | Scenario | Recommended Approach |
  |:---|:---|
  | Quick prototyping | Foundry Agent Service (prompt agent) |
  | Enterprise RAG | Foundry Agent Service + Foundry IQ |
  | Custom orchestration logic | Agent Framework + Workflows |
  | External tool integration | MCP Servers (Foundry or Agent Framework) |
  | Cross-platform agent interop | A2A Protocol |
  | Multi-agent collaboration | Foundry Workflows or Agent Framework Workflows |
  | Specialized compute needs | Hosted Agents (Docker + azd) |

- **What's Next?**
  - Explore the [Foundry Model Catalog](https://ai.azure.com/explore/models)
  - Build production workflows with [Agent Framework](https://learn.microsoft.com/agent-framework/)
  - Dive into [Foundry IQ](https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-foundry-iq)
  - Build and register your own [MCP servers](https://learn.microsoft.com/azure/foundry/mcp/build-your-own-mcp-server)
  - Join the [Azure AI community](https://learn.microsoft.com/azure/ai-services/)

#### Q&A Session

> Open floor for questions, architecture discussions, and next steps for your own agent projects.

---

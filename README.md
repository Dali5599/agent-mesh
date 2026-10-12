<p align="center">
  <img src="./assets/banner.svg" alt="Project Banner" width="100%">
</p>

# Agent-Mesh: High-Performance Distributed Service Mesh for AI Agent Swarms

<p align="center">
  <a href="https://dali5599.github.io/agent-mesh/">
    <img src="https://img.shields.io/badge/Live_Demo-Interactive_Web_App-00c853?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Live Demo">
  </a>
</p>


<div align="center">

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Production-Ready](https://img.shields.io/badge/status-production--ready-success.svg)]()

*A production-ready, highly modular distributed service mesh engineered specifically for complex, multi-tenant AI agent ecosystems.*

</div>

---

## Overview

`agent-mesh` is a cutting-edge infrastructure layer designed to handle the unique coordination, routing, and reliability challenges of autonomous AI agent swarms. Traditional service meshes (like Istio or Linkerd) lack native comprehension of semantic routing, LLM cost attribution, recursive execution bounds, and agent token budgets. 

`agent-mesh` bridges this gap by providing high-performance traffic management, deterministic infinite loop detection, resilient circuit breaking, dynamic rate limiting, complete distributed tracing, and unified control planes tailored for agent-to-agent (A2A) communications.

---

## Key Features

- **Semantic & Dynamic Routing**: Route requests based on agent capabilities, intent models, system loads, and latency thresholds.
- **Deterministic Loop Detection**: Intercept and halt recursive infinite loops in agent swarms using call-stack hashing and token recurrence bounds.
- **Resilient Circuit Breakers**: Protect downstream models and agent nodes from cascading failures with state-machine-backed circuit breakers.
- **Dynamic Rate Limiting**: Enforce token-bucket and sliding-window rate limits at both global and per-agent granularities.
- **End-to-End Distributed Tracing**: Track intent propagation, token consumption, latency, and costs across distributed agent hops.
- **Powerful CLI & REST API**: Full-featured administrative command-line interface and high-performance FastAPI backend for orchestration and control.

---

## Architecture

```
                       +------------------------+
                       |      Agent Mesh CLI    |
                       +-----------+------------+
                                   |
                                   v
+------------------+   +------------------------+   +------------------+
|   AI Agent A     +--->      API Gateway /     +--->   AI Agent B     |
| (Producer Node)  |   |   Orchestration Core   |   | (Consumer Node)  |
+------------------+   +------------------------+   +------------------+
                                   |
         +-------------------------+-------------------------+
         |                         |                         |
         v                         v                         v
+------------------+     +------------------+     +------------------+
|   Loop Breaker   |     | Circuit Breaker  |     |   Rate Limiter   |
+------------------+     +------------------+     +------------------+
         |                         |                         |
         +-------------------------+-------------------------+
                                   |
                                   v
                       +------------------------+
                       |   Distributed Tracer   |
                       +------------------------+
```

---

## Installation

Ensure you are running Python 3.10 or higher. Install the package in editable mode with development dependencies:

```bash
git clone https://github.com/your-org/agent-mesh.git
cd agent-mesh
pip install -e .[dev]
```

---

## Quickstart Guide

### 1. Configuration

Create an operational configuration file named `mesh.yaml`:

```yaml
cluster_name: production-swarm-alpha
node_id: orchestrator-01
host: 0.0.0.0
port: 8000
log_level: INFO

routing:
  default_strategy: load_balanced
  health_check_interval_seconds: 10

resilience:
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout_seconds: 30
  rate_limiter:
    default_requests_per_minute: 120
  loop_breaker:
    max_recursion_depth: 10
```

### 2. Starting the Control Plane & API Server

Launch the high-performance API server using the built-in CLI:

```bash
agent-mesh serve --config mesh.yaml
```

The server will initialize the orchestrator, register core routing tables, and bind to `http://0.0.0.0:8000`.

### 3. Using the CLI

Inspect cluster health, active routes, and metrics via the CLI:

```bash
# Check node status
agent-mesh status --config mesh.yaml

# List registered agents in the mesh
agent-mesh agents list --config mesh.yaml

# Test routing a payload to a target agent
agent-mesh route test --agent-id agent-researcher-01 --payload '{"query": "Analyze Q3 market trends"}'
```

---

## Core Components

### Routing Engine (`agent_mesh.routing`)
Handles dynamic agent discovery, service registration, and intelligent load balancing across multi-zone agent deployments.

### Resilience Layer (`agent_mesh.resilience`)
- **Circuit Breaker**: Prevents hammering failing downstream agents by tripping open after repeated errors.
- **Loop Breaker**: Computes cryptographic hashes of execution paths to instantly abort runaway recursive loops.
- **Rate Limiter**: Controls throughput per agent identity to safeguard API quotas and resource limits.

### Telemetry & Tracing (`agent_mesh.telemetry`)
Provides contextual propagation of trace headers across asynchronous boundaries, recording latency metrics, error frequencies, and token overheads.

---

## REST API Endpoints

Once the server is running, explore the interactive OpenAPI documentation at `http://localhost:8000/docs`.

- `GET /health` - System health check and node readiness.
- `POST /v1/route` - Dispatch an agent execution payload through the mesh.
- `GET /v1/agents` - Retrieve a registry of all active agents and their capabilities.
- `POST /v1/agents/register` - Dynamically register a new agent node into the mesh.

---

## Running Tests

Run the comprehensive test suite using `pytest`:

```bash
pytest -v
```

---

## Contributing

We welcome contributions from the community. Please review our contribution guidelines, open issues for major changes, and ensure all pull requests pass the test suite with 100% coverage on core logic.

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

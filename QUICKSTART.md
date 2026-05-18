# Huawei Cloud MCP Server - Quickstart

Based on the official [HuaweiCloudDeveloper/mcp-server](https://github.com/HuaweiCloudDeveloper/mcp-server) repository.

## Prerequisites

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) package manager
- Huawei Cloud AK/SK credentials

## Setup

```bash
cd /home/nico/ai-projects/huaweicloud-mcp-server

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Install dependencies (creates isolated .venv)
uv sync

# Set credentials
export HUAWEI_ACCESS_KEY="your-access-key"
export HUAWEI_SECRET_KEY="your-secret-key"
```

## Running a Service

### Using the run script

```bash
# Run ECS service with HTTP transport on port 8888
./run.sh ecs http 8888

# Run VPC service with STDIO transport
./run.sh vpc stdio

# Run RDS service with SSE transport on port 9999
./run.sh rds sse 9999
```

### Using uv directly

```bash
# HTTP transport (for Cline, Cursor, etc.)
uv run mcp-server-ecs -t http -p 8888

# STDIO transport (for Claude Desktop, VS Code Copilot, etc.)
uv run mcp-server-ecs -t stdio

# SSE transport
uv run mcp-server-ecs -t sse -p 8888
```

## Available Services

| Service | Command | Description |
|---------|---------|-------------|
| ECS | `mcp-server-ecs` | Elastic Cloud Server |
| VPC | `mcp-server-vpc` | Virtual Private Cloud |
| RDS | `mcp-server-rds` | Relational Database Service |
| IAM | `mcp-server-iam` | Identity and Access Management |
| ELB | `mcp-server-elb` | Elastic Load Balance |
| EIP | `mcp-server-eip` | Elastic IP |
| OBS | `mcp-server-obs` | Object Storage Service |
| CCE | `mcp-server-cce` | Cloud Container Engine |
| EVS | `mcp-server-evs` | Elastic Volume Service |
| DNS | `mcp-server-dns` | Domain Name Service |
| ... | ... | 100+ services available |

## Connecting MCP Clients

### Claude Desktop / VS Code Copilot (STDIO)

Add to your MCP client config (e.g., `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "huaweicloud-ecs": {
      "command": "uv",
      "args": [
        "--directory", "/home/nico/ai-projects/huaweicloud-mcp-server",
        "run", "mcp-server-ecs", "-t", "stdio"
      ],
      "env": {
        "HUAWEI_ACCESS_KEY": "YOUR_ACCESS_KEY",
        "HUAWEI_SECRET_KEY": "YOUR_SECRET_KEY"
      }
    }
  }
}
```

See `mcp-config-stdio.json` for a multi-service example.

### Cline / Cursor (HTTP)

Start the server in HTTP mode first:
```bash
uv run mcp-server-ecs -t http -p 8888
```

Then configure in Cline:
```json
{
  "mcpServers": {
    "huaweicloud-ecs": {
      "url": "http://localhost:8888/mcp",
      "type": "streamableHttp"
    }
  }
}
```

See `mcp-config-http.json` for an example.

## Running Tests

```bash
# Run all tests (162 tests)
uv run pytest tests/ -v

# Run only unit tests
uv run pytest tests/unit/ -v

# Run only integration tests (tests real service configs)
uv run pytest tests/integration/ -v

# Run only E2E transport tests
uv run pytest tests/e2e/ -v

# Run with coverage
uv run pytest tests/ -v --tb=short
```

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures and test data
├── unit/
│   ├── test_openapi_converter.py  # OpenAPI → MCP Tools conversion (19 tests)
│   ├── test_hwc_tools.py         # SDK client, config, HTTP info (28 tests)
│   ├── test_model.py             # MCPConfig dataclass (11 tests)
│   ├── test_server.py            # MCPServer init, tools, clients (14 tests)
│   └── test_variable.py          # Constants (6 tests)
├── integration/
│   └── test_services.py          # Real service configs: ECS, VPC, RDS, IAM, ELB, EIP (72 tests)
├── e2e/
│   └── test_transport.py         # Transport mode creation (4 tests)
└── helpers/
    └── mock_sdk.py               # Mock SDK utilities
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HUAWEI_ACCESS_KEY` | Huawei Cloud Access Key | Required |
| `HUAWEI_SECRET_KEY` | Huawei Cloud Secret Key | Required |
| `MCP_SERVER_MODE` | Transport mode: `stdio`, `http`, `sse` | From config.yaml |
| `MCP_SERVER_PORT` | Port for HTTP/SSE transport | From config.yaml |

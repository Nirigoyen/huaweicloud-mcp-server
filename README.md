# Huawei Cloud MCP Server

A Model Context Protocol (MCP) server for Huawei Cloud, enabling AI assistants to manage cloud resources through natural conversation. Supports 170+ services including ECS, VPC, RDS, IAM, OBS, and more.

## Features

- **170+ Huawei Cloud services** as MCP tools, auto-generated from OpenAPI specs
- **Gateway server** — access all services through 4 meta-tools instead of 11,000+ individual tools, saving context window space
- **Global region support** — works with all Huawei Cloud regions (Santiago, São Paulo, Hong Kong, etc.) via `HUAWEI_REGION` env var
- **Region in tool schemas** — every tool exposes a `region` parameter so LLMs can target any region per-call
- **Docker ready** — Dockerfile and docker-compose included for one-command deployment
- **Multiple transports** — stdio, HTTP (StreamableHTTP), and SSE

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended) or pip

### 1. Set credentials

```bash
export HUAWEI_ACCESS_KEY="your-access-key"
export HUAWEI_SECRET_KEY="your-secret-key"
export HUAWEI_REGION="la-south-2"  # optional, defaults to cn-north-4
```

### 2. Run a service

```bash
# Clone the repo
git clone https://github.com/Nirigoyen/huaweicloud-mcp-server.git
cd huaweicloud-mcp-server

# Run individual service (e.g. ECS)
uv run mcp-server-ecs

# Run with HTTP transport on port 8888
uv run mcp-server-ecs -t http -p 8888

# Run the gateway server (all services via 4 meta-tools)
uv run mcp-server-gateway -t http -p 8888
```

### 3. Configure your MCP client

**Stdio transport** (for Claude Desktop, Cursor, etc.):

```json
{
  "mcpServers": {
    "huaweicloud-gateway": {
      "command": "uv",
      "args": ["--directory", "/path/to/huaweicloud-mcp-server", "run", "mcp-server-gateway", "-t", "stdio"],
      "env": {
        "HUAWEI_ACCESS_KEY": "YOUR_ACCESS_KEY",
        "HUAWEI_SECRET_KEY": "YOUR_SECRET_KEY",
        "HUAWEI_REGION": "la-south-2"
      }
    }
  }
}
```

**HTTP transport** (for Cline, custom clients):

```json
{
  "mcpServers": {
    "huaweicloud-gateway": {
      "url": "http://localhost:8888/mcp",
      "type": "streamableHttp"
    }
  }
}
```

## Gateway Server

The gateway server provides a **tree-like** structure for accessing all 170+ services through just 4 meta-tools. This keeps your context window small — instead of loading thousands of tools, the AI discovers and invokes them on demand.

### Meta-Tools

| Tool | Description |
|------|-------------|
| `list_available_services()` | List all available services with name, description, and tool count |
| `list_service_tools(service)` | Get all tools + schemas for a specific service |
| `call_service_tool(service, tool_name, arguments)` | Invoke any tool from any service |
| `search_tools(query)` | Search for tools across all services by keyword |

### Example Workflow

```
1. list_available_services()
   → [{service: "ecs", tool_count: 106}, {service: "vpc", tool_count: 184}, ...]

2. list_service_tools(service="ecs")
   → [{name: "ListServersDetails", inputSchema: {...}}, ...]

3. call_service_tool(
     service="ecs",
     tool_name="ListServersDetails",
     arguments={"project_id": "abc123", "region": "la-south-2"}
   )
   → [{servers: [...]}]
```

### Why use the gateway?

| | Individual services | Gateway server |
|---|---|---|
| Tools in context | 50–900 per service | **4 (constant)** |
| Context usage | High (grows with service count) | **Minimal** |
| Service access | One service per server | **All 170+ services** |
| Tool discovery | All tools loaded upfront | **On-demand, lazy-loaded** |

## Region Support

Region determines which Huawei Cloud datacenter to target. Resolution priority:

1. **Tool argument** — `region` parameter in the tool call (visible in every tool's schema)
2. **`HUAWEI_REGION` env var** — global default for all calls
3. **`cn-north-4`** — hardcoded fallback

### Available Regions

| Region | ID |
|--------|-----|
| China North 4 (Beijing) | `cn-north-4` |
| China North 1 (Beijing) | `cn-north-1` |
| China East 2 (Shanghai) | `cn-east-2` |
| China East 3 (Shanghai) | `cn-east-3` |
| China South 1 (Guangzhou) | `cn-south-1` |
| AP Southeast 1 (Hong Kong) | `ap-southeast-1` |
| AP Southeast 2 (Bangkok) | `ap-southeast-2` |
| AP Southeast 3 (Singapore) | `ap-southeast-3` |
| LA South 2 (Santiago) | `la-south-2` |
| SA Brazil 1 (São Paulo) | `sa-brazil-1` |
| AF South 1 (Johannesburg) | `af-south-1` |
| TR West 1 (Istanbul) | `tr-west-1` |
| ME East 1 (Bahrain) | `me-east-1` |

## Docker

### Build and run the gateway

```bash
# Build
docker compose build

# Run gateway (HTTP on port 8888)
HUAWEI_ACCESS_KEY=your-ak HUAWEI_SECRET_KEY=your-sk HUAWEI_REGION=la-south-2 \
  docker compose up

# Run with individual services (ecs, vpc, rds, iam)
HUAWEI_ACCESS_KEY=your-ak HUAWEI_SECRET_KEY=your-sk \
  docker compose --profile individual up
```

### Run a specific service

```bash
docker run -e HUAWEI_ACCESS_KEY=your-ak \
           -e HUAWEI_SECRET_KEY=your-sk \
           -e HUAWEI_REGION=la-south-2 \
           -e SERVICE=ecs \
           -p 8888:8888 \
           huaweicloud-mcp-server
```

### docker-compose services

| Service | Port | Profile | Description |
|---------|------|---------|-------------|
| `gateway` | 8888 | default | All services via 4 meta-tools |
| `ecs` | 8889 | `individual` | ECS service only |
| `vpc` | 8890 | `individual` | VPC service only |
| `rds` | 8891 | `individual` | RDS service only |
| `iam` | 8892 | `individual` | IAM service only |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HUAWEI_ACCESS_KEY` | Yes | — | Huawei Cloud AK credential |
| `HUAWEI_SECRET_KEY` | Yes | — | Huawei Cloud SK credential |
| `HUAWEI_REGION` | No | `cn-north-4` | Default region for all API calls |
| `MCP_SERVER_MODE` | No | from config | Transport mode: `stdio`, `http`, `sse` |
| `MCP_SERVER_PORT` | No | from config | Port for HTTP/SSE transport |

## Supported Services

170+ Huawei Cloud services are supported. Here are the most commonly used:

| Category | Service | Code | Tools |
|----------|---------|------|-------|
| **Compute** | Elastic Cloud Server | `ecs` | 106 |
| **Compute** | Image Management Service | `ims` | 46 |
| **Compute** | Auto Scaling | `as` | 62 |
| **Compute** | FunctionGraph | `functiongraph` | — |
| **Networking** | Virtual Private Cloud | `vpc` | 184 |
| **Networking** | Elastic IP | `eip` | 61 |
| **Networking** | Elastic Load Balance | `elb` | 122 |
| **Networking** | NAT Gateway | `nat` | 53 |
| **Networking** | DNS | `dns` | 87 |
| **Networking** | VPN | `vpn` | 76 |
| **Storage** | Elastic Volume Service | `evs` | 31 |
| **Storage** | Object Storage Service | `obs` | 81 |
| **Storage** | Cloud Backup and Recovery | `cbr` | 71 |
| **Database** | Relational Database Service | `rds` | 232 |
| **Database** | GaussDB | `gaussdb` | 212 |
| **Database** | Document Database Service | `dds` | 123 |
| **Database** | Distributed Cache Service | `dcs` | 137 |
| **Security** | Key Management Service | `kms` | 58 |
| **Security** | Web Application Firewall | `waf` | — |
| **Security** | Host Security Service | `hss` | 237 |
| **Management** | Identity and Access Management | `iam` | 152 |
| **Management** | Cloud Eye (CES) | `ces` | 71 |
| **Management** | Simple Message Notification | `smn` | 53 |
| **Analytics** | Data Warehouse Service | `dws` | 195 |
| **Analytics** | DataArts Studio | `dataartsstudio` | 373 |

Run the gateway and call `list_available_services()` to see all 170+ services.

## Architecture

```
assets/utils/
├── server.py          # MCPServer — loads OpenAPI spec → MCP tools
├── gateway.py         # MCPGatewayServer — 4 meta-tools for all services
├── openapi.py         # OpenAPIToToolsConverter — OpenAPI 3.0 → MCP Tools
├── hwc_tools.py       # CustomClient, create_api_client(), build_http_info()
├── model.py           # MCPConfig dataclass
└── variable.py        # Environment variable constants

huaweicloud_services_server/
├── mcp_server_ecs/    # Each service: run.py + config.yaml + {service}.json
├── mcp_server_vpc/
├── mcp_server_rds/
├── ...
└── mcp_server_gateway/  # Gateway entry point
```

Each service's OpenAPI JSON spec is the **source of truth** for its tools — tools are generated at runtime, not hardcoded in Python.

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check .
uv run ruff format .

# Run a service
uv run mcp-server-ecs -t http -p 8888
```

## License

MIT

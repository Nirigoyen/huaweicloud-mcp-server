# Huawei Cloud MCP Server

## Commands

```bash
uv sync                              # install dependencies
uv run mcp-server-ecs                # run a service (any of 80+ registered names)
uv run mcp-server-ecs -t http -p 8888  # override transport/port
uv run mcp-server-gateway            # run the gateway server (all services via 4 meta-tools)
uv run mcp-server-gateway -t http -p 8888  # gateway with HTTP transport
uv run pytest tests/ -v              # all tests
uv run pytest tests/unit/ -v         # unit only
uv run pytest tests/integration/ -v  # integration only
uv run pytest tests/e2e/ -v          # e2e only
uv run ruff check .                  # lint
uv run ruff format --check .         # format check
uv run ruff format .                 # apply formatting
```

## Architecture

This is a monorepo with a single `pyproject.toml`. All 100+ Huawei Cloud service MCP servers share one build, one version (`0.3.0`), and one framework.

**Core framework** lives in `assets/utils/`:
- `server.py` — `MCPServer` class: loads config, converts OpenAPI spec to MCP tools, registers handlers, runs transport
- `gateway.py` — `MCPGatewayServer` class: tree-like gateway that exposes 4 meta-tools for discovering and invoking any service's tools on demand
- `openapi.py` — `OpenAPIToToolsConverter` + `SwaggerRefResolver`: converts OpenAPI 3.0 specs into MCP `Tool` objects at runtime
- `hwc_tools.py` — `CustomClient` (extends Huawei SDK), `create_api_client()`, `build_http_info()`, `load_config()`
- `model.py` — `MCPConfig` dataclass
- `variable.py` — env var name constants

**Each service** in `huaweicloud_services_server/mcp_server_{name}/` is just:
- `run.py` — identical boilerplate, calls `assets.utils.run_server()`
- `config/config.yaml` — `service_code`, `transport`, `port`
- `config/{service}.json` — **the OpenAPI spec is the source of truth for all tools** (tools are NOT defined in Python)

**How a tool call works:** `call_tool()` → reads `region` from args (priority: tool arg → HUAWEI_REGION env → `cn-north-4` default) → creates SDK client with AK/SK → `build_http_info()` maps tool name to OpenAPI path's `x-method`/`x-url` → `client.do_http_request()` → returns JSON

## Gateway Server

The gateway server (`mcp-server-gateway`) provides a **tree-like** structure for accessing all 170+ services through just 4 meta-tools, saving context window space.

### Meta-Tools

| Tool | Purpose |
|------|---------|
| `list_available_services()` | Returns all services with name, description, tool count, endpoint info |
| `list_service_tools(service, include_schemas?)` | Returns tools + schemas for a specific service |
| `call_service_tool(service, tool_name, arguments)` | Invokes a tool from any service |
| `search_tools(query, service?)` | Search across services by keyword |

### Typical Agent Workflow

```
1. list_available_services()
   → [{service: "ecs", tool_count: 106}, {service: "vpc", tool_count: 184}, ...]

2. list_service_tools(service="ecs")
   → [{name: "list_servers", description: "...", inputSchema: {...}}, ...]

3. call_service_tool(service="ecs", tool_name="list_servers",
     arguments={"project_id": "abc123", "region": "la-south-2"})
   → API response
```

### Key Design Points

- **4 tools in context** instead of 11,784 — constant footprint regardless of how many services exist
- **Lazy loading** — OpenAPI specs are only loaded when `list_service_tools` or `call_service_tool` is called, then cached
- **Region support** — `call_service_tool` respects the same region priority as individual servers
- **Search** — `search_tools` lets agents find relevant tools without knowing which service they belong to

## Adding a new service

1. Create `huaweicloud_services_server/mcp_server_{name}/src/mcp_server_{name}/run.py` (copy any existing one)
2. Create `config/config.yaml` and `config/{name}.json` (OpenAPI spec with `x-host`, `x-method`, `x-url` extensions)
3. Add **three** entries to `pyproject.toml`:
   - `[tool.setuptools].packages` — the package path
   - `[tool.setuptools.package-data]` — `config/*.yaml` and `config/*.json`
   - `[project.scripts]` — `mcp-server-{name}` console script entrypoint
4. Missing any of the three `pyproject.toml` entries = broken service

## OpenAPI spec conventions

The JSON specs use **Huawei Cloud extensions** (not standard OpenAPI):
- `info.x-host` — endpoint template, e.g. `ecs.{region}.myhuaweicloud.com`
- `x-method` — HTTP method per path
- `x-url` — actual API path with `{endpoint}` placeholder

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `HUAWEI_ACCESS_KEY` | Yes | AK credential (tool calls fail without it) |
| `HUAWEI_SECRET_KEY` | Yes | SK credential (tool calls fail without it) |
| `HUAWEI_REGION` | No | Default region for all API calls (e.g. `la-south-2`, `cn-north-4`). Falls back to `cn-north-4` if not set |
| `MCP_SERVER_MODE` | No | Override transport: `stdio`, `http`, `sse` |
| `MCP_SERVER_PORT` | No | Override port for HTTP/SSE |

Env vars override `config.yaml` values.

## Region handling

Region determines which Huawei Cloud datacenter to target. The resolution priority is:

1. **Tool argument** — `region` parameter passed in the tool call (visible in each tool's `inputSchema`)
2. **`HUAWEI_REGION` env var** — global default for all tool calls
3. **`cn-north-4`** — hardcoded fallback

Common region IDs:

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

## Testing

- pytest + pytest-asyncio (`asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed)
- Integration tests are parametrized over `["ecs", "vpc", "rds", "iam", "elb", "eip"]` and validate real service config files
- No coverage tool configured. No CI test execution — tests run locally only.

## Gotchas

- **`region` is injected into every tool's inputSchema** — agents can see and pass it as a parameter
- **Region priority**: tool argument > `HUAWEI_REGION` env var > `cn-north-4` default
- **`filter_parameters()` strips `None` and empty lists** before API calls — safe to omit optional params
- **SSL verification is disabled** in SDK client (`ignore_ssl_verification = True`)
- **`fastmcp>=2.0.0`** is a dependency but code uses the lower-level `mcp.server` API directly; fastmcp is only used for logging utilities
- **`huaweicloud_dws_mcp_inner/`** is a separate project with its own `pyproject.toml` — not part of the main build
- **CI only runs ruff** (`ruff check .` + `ruff format --check .`), no tests in CI
- **Commit convention:** signed commits required (`git commit -s`), branches: `add-xxx` / `fix-xxx`
- **Code comments and log messages are in Chinese**; variable names and public API are in English
- **`uv.lock` is in `.gitignore`** but exists in repo root — inconsistency
- **Line length:** 120 (configured in `pyproject.toml [tool.ruff]`)

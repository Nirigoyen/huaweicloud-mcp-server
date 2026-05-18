FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml .
COPY assets/ assets/
COPY huaweicloud_services_server/ huaweicloud_services_server/
COPY common_servers/ common_servers/
COPY huaweicloud_marketplace_server/ huaweicloud_marketplace_server/

RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

ENV SERVICE=gateway
ENV MCP_SERVER_MODE=http
ENV MCP_SERVER_PORT=8888

EXPOSE 8888

CMD ["sh", "-c", "uv run mcp-server-${SERVICE} -t ${MCP_SERVER_MODE} -p ${MCP_SERVER_PORT}"]

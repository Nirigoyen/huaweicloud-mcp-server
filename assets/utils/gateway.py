import asyncio
import contextlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional, AsyncIterator

import uvicorn
from huaweicloudsdkcore.exceptions.exceptions import ClientRequestException
from mcp.server import Server
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.utilities.logging import configure_logging, get_logger
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

from .hwc_tools import (
    create_api_client,
    build_http_info,
    load_openapi,
    filter_parameters,
    load_config,
)
from .model import MCPConfig
from .openapi import OpenAPIToToolsConverter
from .variable import TRANSPORT_SSE, TRANSPORT_HTTP, HUAWEI_REGION

logger = get_logger(__name__)
configure_logging("INFO")

DEFAULT_REGION = "cn-north-4"

REGION_SCHEMA = {
    "type": "string",
    "description": (
        "Huawei Cloud region ID. Examples: cn-north-4, cn-north-1, cn-east-2, "
        "ap-southeast-1, ap-southeast-2, la-south-2, sa-brazil-1, af-south-1, "
        "tr-west-1, me-east-1. Falls back to HUAWEI_REGION env var or cn-north-4."
    ),
}


class ServiceInfo:
    __slots__ = ("service_code", "title", "x_host", "tool_count", "config_path", "openapi_path", "has_region")

    def __init__(self, service_code, title, x_host, tool_count, config_path, openapi_path, has_region):
        self.service_code = service_code
        self.title = title
        self.x_host = x_host
        self.tool_count = tool_count
        self.config_path = config_path
        self.openapi_path = openapi_path
        self.has_region = has_region


class MCPGatewayServer:
    def __init__(self, config_path: Path, services_root: Optional[Path] = None):
        self.config_path = config_path

        self.config: Optional[MCPConfig] = None
        self.server: Optional[Server] = None
        self.initialized: bool = False

        self.services_root = services_root
        self.service_registry: dict[str, ServiceInfo] = {}
        self._openapi_cache: dict[str, dict[str, Any]] = {}
        self._tools_cache: dict[str, list[Tool]] = {}

        self.active_clients: dict[str, Any] = {}
        self._clients_lock = asyncio.Lock()

        self.initialize()

    def initialize(self) -> None:
        if self.initialized:
            return

        logger.info("开始初始化MCP网关服务器...")

        try:
            self.config = load_config(self.config_path)
            if not self.config:
                raise ValueError("无法加载服务器配置")

            self.server = Server("hwc-mcp-server-gateway")
            logger.info("初始化MCP网关服务器实例：hwc-mcp-server-gateway")

            if not self.services_root:
                self.services_root = Path(self.config_path).parent.parent.parent.parent.parent

            self._build_service_registry()

            self._register_tool_handlers()

            self.initialized = True
            logger.info(f"MCP网关服务器初始化完成，发现 {len(self.service_registry)} 个服务")

        except Exception as e:
            logger.error(f"服务器初始化失败: {e}")
            raise

    def _build_service_registry(self) -> None:
        logger.info(f"扫描服务目录: {self.services_root}")
        if not self.services_root or not self.services_root.exists():
            logger.warning(f"服务目录不存在: {self.services_root}")
            return

        for service_dir in sorted(self.services_root.iterdir()):
            if not service_dir.is_dir():
                continue
            if not service_dir.name.startswith("mcp_server_"):
                continue

            service_code = service_dir.name.replace("mcp_server_", "", 1)
            config_subdir = service_dir / "src" / service_dir.name / "config"
            config_yaml = config_subdir / "config.yaml"
            openapi_json = config_subdir / f"{service_code}.json"

            if not config_yaml.exists() or not openapi_json.exists():
                continue

            try:
                info = self._peek_openapi_metadata(openapi_json)
                if info is None:
                    continue

                title, x_host, tool_count, has_region = info
                self.service_registry[service_code] = ServiceInfo(
                    service_code=service_code,
                    title=title,
                    x_host=x_host,
                    tool_count=tool_count,
                    config_path=config_yaml,
                    openapi_path=openapi_json,
                    has_region=has_region,
                )
            except Exception as e:
                logger.warning(f"跳过服务 {service_code}: {e}")

    @staticmethod
    def _peek_openapi_metadata(openapi_path: Path) -> Optional[tuple]:
        try:
            with open(openapi_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

        info = data.get("info", {})
        title = info.get("title", "")
        x_host = info.get("x-host", "")
        has_region = "{region}" in x_host

        paths = data.get("paths", {})
        tool_count = 0
        if isinstance(paths, dict):
            for path_val in paths.values():
                if not isinstance(path_val, dict):
                    continue
                for key in path_val:
                    if key in ("get", "put", "post", "delete", "patch", "options", "head"):
                        tool_count += 1

        return title, x_host, tool_count, has_region

    def _get_or_load_openapi(self, service_code: str) -> Optional[dict[str, Any]]:
        if service_code in self._openapi_cache:
            return self._openapi_cache[service_code]

        svc = self.service_registry.get(service_code)
        if not svc:
            return None

        try:
            openapi_dict = load_openapi(svc.openapi_path)
            self._openapi_cache[service_code] = openapi_dict
            return openapi_dict
        except Exception as e:
            logger.error(f"加载服务 {service_code} OpenAPI失败: {e}")
            return None

    def _get_or_load_tools(self, service_code: str) -> Optional[list[Tool]]:
        if service_code in self._tools_cache:
            return self._tools_cache[service_code]

        openapi_dict = self._get_or_load_openapi(service_code)
        if not openapi_dict:
            return None

        try:
            tools = OpenAPIToToolsConverter(openapi_dict).convert()
            self._tools_cache[service_code] = tools
            return tools
        except Exception as e:
            logger.error(f"转换服务 {service_code} 工具失败: {e}")
            return None

    def _resolve_region(self, arguments: dict) -> str:
        return arguments.get("region") or self.config.region or os.environ.get(HUAWEI_REGION) or DEFAULT_REGION

    async def register_client(self, client_id, request):
        async with self._clients_lock:
            self.active_clients[client_id] = {
                "request": request,
                "connected_at": time.time(),
            }
            logger.info(f"客户端注册成功: {client_id}")

    async def unregister_client(self, client_id):
        async with self._clients_lock:
            if client_id in self.active_clients:
                del self.active_clients[client_id]
                logger.info(f"客户端已注销: {client_id}")
            else:
                logger.warning(f"尝试注销不存在的客户端: {client_id}")

    def _register_tool_handlers(self) -> None:
        if not self.server:
            raise RuntimeError("服务器未初始化")

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            self._ensure_initialized()
            return self._build_gateway_tools()

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent | EmbeddedResource]:
            self._ensure_initialized()

            if name == "list_available_services":
                return self._handle_list_available_services()
            elif name == "list_service_tools":
                return self._handle_list_service_tools(arguments)
            elif name == "call_service_tool":
                return await self._handle_call_service_tool(arguments)
            elif name == "search_tools":
                return self._handle_search_tools(arguments)
            else:
                raise ToolError(f"未知工具: {name}")

    def _build_gateway_tools(self) -> list[Tool]:
        return [
            Tool(
                name="list_available_services",
                description=(
                    "List all available Huawei Cloud services. Returns service name, "
                    "description, tool count, and endpoint info for each service. "
                    "Use this to discover which services are available before using "
                    "list_service_tools or call_service_tool."
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="list_service_tools",
                description=(
                    "List all tools for a specific Huawei Cloud service. Returns tool "
                    "names, descriptions, and input schemas. Use this after "
                    "list_available_services to see what operations a service supports."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "Service code (e.g. 'ecs', 'vpc', 'rds', 'iam')",
                        },
                        "include_schemas": {
                            "type": "boolean",
                            "description": "Whether to include full inputSchema for each tool (default: true). Set to false for a lighter response with just names and descriptions.",
                            "default": True,
                        },
                    },
                    "required": ["service"],
                },
            ),
            Tool(
                name="call_service_tool",
                description=(
                    "Invoke a tool from a specific Huawei Cloud service. Use this to "
                    "execute any API operation after discovering it via "
                    "list_service_tools. The region parameter controls which Huawei "
                    "Cloud region to target."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "Service code (e.g. 'ecs', 'vpc', 'rds')",
                        },
                        "tool_name": {
                            "type": "string",
                            "description": "Name of the tool to invoke (from list_service_tools)",
                        },
                        "arguments": {
                            "type": "object",
                            "description": "Arguments for the tool. Include 'region' to specify the Huawei Cloud region. Include 'project_id' and other params as needed.",
                        },
                    },
                    "required": ["service", "tool_name", "arguments"],
                },
            ),
            Tool(
                name="search_tools",
                description=(
                    "Search for tools across all services by keyword. Returns matching "
                    "tools with their service, name, and description. Useful for "
                    "finding the right tool when you're not sure which service it belongs to."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search keyword to match against tool names and descriptions",
                        },
                        "service": {
                            "type": "string",
                            "description": "Optional: limit search to a specific service code",
                        },
                    },
                    "required": ["query"],
                },
            ),
        ]

    def _handle_list_available_services(self) -> list[TextContent]:
        services = []
        for code, svc in sorted(self.service_registry.items()):
            services.append(
                {
                    "service": code,
                    "title": svc.title,
                    "tool_count": svc.tool_count,
                    "x_host": svc.x_host,
                    "has_region": svc.has_region,
                }
            )
        return [TextContent(type="text", text=json.dumps(services, indent=2, ensure_ascii=False))]

    def _handle_list_service_tools(self, arguments: dict) -> list[TextContent]:
        service_code = arguments.get("service", "")
        include_schemas = arguments.get("include_schemas", True)

        svc = self.service_registry.get(service_code)
        if not svc:
            available = sorted(self.service_registry.keys())
            error = {
                "error": f"Service '{service_code}' not found",
                "available_services": available[:20],
                "hint": "Use list_available_services to see all services",
            }
            return [TextContent(type="text", text=json.dumps(error, indent=2, ensure_ascii=False))]

        tools = self._get_or_load_tools(service_code)
        if tools is None:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": f"Failed to load tools for service '{service_code}'"}, indent=2),
                )
            ]

        result = []
        for tool in tools:
            entry = {"name": tool.name, "description": tool.description}
            if include_schemas:
                entry["inputSchema"] = tool.inputSchema
            result.append(entry)

        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    async def _handle_call_service_tool(self, arguments: dict) -> list[TextContent]:
        service_code = arguments.get("service", "")
        tool_name = arguments.get("tool_name", "")
        tool_arguments = arguments.get("arguments", {})

        if not isinstance(tool_arguments, dict):
            return [TextContent(type="text", text=json.dumps({"error": "'arguments' must be a JSON object"}, indent=2))]

        svc = self.service_registry.get(service_code)
        if not svc:
            return [
                TextContent(type="text", text=json.dumps({"error": f"Service '{service_code}' not found"}, indent=2))
            ]

        ak = self.config.ak
        sk = self.config.sk
        if not ak or not sk:
            error_msg = {
                "code": "MISSING_CREDENTIALS",
                "message": "HUAWEI_ACCESS_KEY or HUAWEI_SECRET_KEY not configured",
            }
            raise ToolError(error_msg)

        region = self._resolve_region(tool_arguments)
        x_host = svc.x_host

        openapi_dict = self._get_or_load_openapi(service_code)
        tools = self._get_or_load_tools(service_code)

        if not openapi_dict or not tools:
            return [
                TextContent(
                    type="text", text=json.dumps({"error": f"Failed to load service '{service_code}'"}, indent=2)
                )
            ]

        client = create_api_client(ak, sk, x_host, region)
        try:
            filtered_args = filter_parameters(tool_arguments)
            http_info = build_http_info(tool_name, filtered_args, openapi_dict, tools)
            response = client.do_http_request(**http_info)
            response_data = response.json() if response and response.content else {}
            return [
                TextContent(
                    type="text",
                    text=json.dumps(response_data, indent=2, ensure_ascii=False),
                )
            ]
        except ClientRequestException as ex:
            logger.error(f"API 请求失败: {ex.error_msg}")
            raise ValueError(ex.error_msg)
        except Exception as ex:
            logger.error(f"意外的错误: {str(ex)}")
            raise

    def _handle_search_tools(self, arguments: dict) -> list[TextContent]:
        query = arguments.get("query", "").lower()
        service_filter = arguments.get("service")

        if not query:
            return [TextContent(type="text", text=json.dumps({"error": "query parameter is required"}, indent=2))]

        results = []
        services_to_search = (
            {service_filter: self.service_registry[service_filter]}
            if service_filter and service_filter in self.service_registry
            else self.service_registry
        )

        for code, svc in services_to_search.items():
            tools = self._get_or_load_tools(code)
            if not tools:
                continue

            for tool in tools:
                name_match = query in tool.name.lower()
                desc_match = query in (tool.description or "").lower()
                if name_match or desc_match:
                    results.append(
                        {
                            "service": code,
                            "name": tool.name,
                            "description": tool.description[:200] if tool.description else "",
                        }
                    )

        results.sort(key=lambda x: (0 if query in x["name"] else 1, x["service"], x["name"]))

        return [TextContent(type="text", text=json.dumps(results[:50], indent=2, ensure_ascii=False))]

    def _ensure_initialized(self) -> None:
        if not self.initialized:
            raise RuntimeError("服务器未初始化")

    async def run_server(self):
        self._ensure_initialized()
        if self.config.transport == TRANSPORT_SSE:
            await self.run_sse_server()
        elif self.config.transport == TRANSPORT_HTTP:
            await self.run_http_server()
        else:
            await self.run_stdio_server()

    async def run_sse_server(self):
        logger.info("启动SSE网关服务器")
        sse = SseServerTransport("/messages/")

        async def handle_sse_connection(request):
            logger.info(f"SSE连接请求来自: {request.client}")

            if not self.initialized:
                return JSONResponse({"error": "Server initializing"}, status_code=503)

            client_id = str(uuid.uuid4())
            connection_active = True

            try:
                await self.register_client(client_id, request)

                async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                    input_stream, output_stream = streams

                    try:
                        await self.server.run(
                            input_stream,
                            output_stream,
                            self.server.create_initialization_options(),
                        )

                    except asyncio.CancelledError:
                        logger.info(f"SSE任务被取消: {client_id}")
                        connection_active = False

                    except Exception as e:
                        logger.error(f"SSE通信异常: {e}", exc_info=True)
                        connection_active = False

                        if not output_stream.closed:
                            try:
                                error_msg = {
                                    "event": "error",
                                    "data": {"message": str(e), "code": 500},
                                }
                                await output_stream.send(json.dumps(error_msg))
                            except Exception as send_error:
                                logger.warning(f"发送错误信息失败: {send_error}")

                    finally:
                        if connection_active:
                            connection_active = False
                            await self.unregister_client(client_id)
                            logger.info(f"SSE连接已关闭: {client_id}")

            except Exception as e:
                logger.error(f"SSE连接建立失败: {e}", exc_info=True)

                return JSONResponse(
                    {"error": "Failed to establish SSE connection", "details": str(e)},
                    status_code=500,
                )

            return JSONResponse({"status": "SSE connection closed normally"}, status_code=200)

        app = Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse_connection),
                Mount("/messages/", app=sse.handle_post_message),
            ],
            debug=True,
        )

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_headers=["*"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        )
        sse_config = uvicorn.Config(app, host="0.0.0.0", port=self.config.port)
        sse_server = uvicorn.Server(sse_config)
        await sse_server.serve()

    async def run_stdio_server(self):
        logger.info("启动STDIO网关服务器")
        async with stdio_server() as streams:
            await self.server.run(streams[0], streams[1], self.server.create_initialization_options())

    async def run_http_server(self):
        logger.info("启动StreamableHTTP网关服务器")
        session_manager = StreamableHTTPSessionManager(
            app=self.server,
            event_store=None,
            stateless=True,
        )

        async def handle_streamable_http(scope: Scope, receive: Receive, send: Send) -> None:
            await session_manager.handle_request(scope, receive, send)

        @contextlib.asynccontextmanager
        async def lifespan(app: Starlette) -> AsyncIterator[None]:
            async with session_manager.run():
                logger.info("Application started with StreamableHTTP session manager!")
                try:
                    yield
                finally:
                    logger.info("Application shutting down...")

        starlette_app = Starlette(
            debug=True,
            routes=[
                Mount("/mcp", app=handle_streamable_http),
            ],
            lifespan=lifespan,
        )

        http_config = uvicorn.Config(starlette_app, host="0.0.0.0", port=self.config.port)
        http_server = uvicorn.Server(http_config)
        await http_server.serve()

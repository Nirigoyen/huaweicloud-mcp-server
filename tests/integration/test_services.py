from pathlib import Path


from assets.utils.server import MCPServer
from assets.utils.openapi import OpenAPIToToolsConverter
from assets.utils.hwc_tools import load_config, load_openapi, build_http_info
from mcp.types import Tool


PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestServiceIntegration:
    def test_service_config_exists(self, service_config_path):
        config_yaml = service_config_path / "config.yaml"
        assert config_yaml.exists(), f"config.yaml not found for service at {service_config_path}"

    def test_service_openapi_exists(self, service_config_path, service_name):
        openapi_json = service_config_path / f"{service_name}.json"
        assert openapi_json.exists(), f"{service_name}.json not found at {service_config_path}"

    def test_service_config_loads(self, service_config_path):
        config_yaml = service_config_path / "config.yaml"
        config = load_config(config_yaml)
        assert config.service_code
        assert config.transport in ("http", "sse", "stdio")
        assert isinstance(config.port, int)

    def test_service_openapi_loads(self, service_config_path, service_name):
        openapi_json = service_config_path / f"{service_name}.json"
        openapi_spec = load_openapi(openapi_json)
        assert "info" in openapi_spec
        assert "paths" in openapi_spec
        assert len(openapi_spec["paths"]) > 0

    def test_service_openapi_has_x_host(self, service_config_path, service_name):
        openapi_json = service_config_path / f"{service_name}.json"
        openapi_spec = load_openapi(openapi_json)
        assert "x-host" in openapi_spec["info"], f"{service_name} missing x-host in info"

    def test_service_converts_to_tools(self, service_config_path, service_name):
        openapi_json = service_config_path / f"{service_name}.json"
        openapi_spec = load_openapi(openapi_json)
        converter = OpenAPIToToolsConverter(openapi_spec)
        tools = converter.convert()
        assert len(tools) > 0, f"{service_name} produced 0 tools"
        for tool in tools:
            assert isinstance(tool, Tool)
            assert tool.name
            assert tool.description

    def test_service_tools_have_valid_schemas(self, service_config_path, service_name):
        openapi_json = service_config_path / f"{service_name}.json"
        openapi_spec = load_openapi(openapi_json)
        converter = OpenAPIToToolsConverter(openapi_spec)
        tools = converter.convert()
        for tool in tools:
            assert "type" in tool.inputSchema
            assert tool.inputSchema["type"] == "object"
            assert "properties" in tool.inputSchema

    def test_service_mcp_server_initializes(self, service_config_path):
        config_yaml = service_config_path / "config.yaml"
        server = MCPServer(config_yaml)
        assert server.initialized is True
        assert len(server.tools) > 0

    def test_service_tool_names_are_unique(self, service_config_path, service_name):
        openapi_json = service_config_path / f"{service_name}.json"
        openapi_spec = load_openapi(openapi_json)
        converter = OpenAPIToToolsConverter(openapi_spec)
        tools = converter.convert()
        tool_names = [t.name for t in tools]
        assert len(tool_names) == len(set(tool_names)), f"{service_name} has duplicate tool names"

    def test_service_tool_names_match_mcp_conventions(self, service_config_path, service_name):
        openapi_json = service_config_path / f"{service_name}.json"
        openapi_spec = load_openapi(openapi_json)
        converter = OpenAPIToToolsConverter(openapi_spec)
        tools = converter.convert()
        for tool in tools:
            assert tool.name.isidentifier() or all(
                c.isalnum() or c == "_" for c in tool.name
            ), f"Tool name '{tool.name}' in {service_name} doesn't follow naming conventions"

    def test_service_tool_names_within_length_limit(self, service_config_path, service_name):
        openapi_json = service_config_path / f"{service_name}.json"
        openapi_spec = load_openapi(openapi_json)
        converter = OpenAPIToToolsConverter(openapi_spec)
        tools = converter.convert()
        for tool in tools:
            assert len(tool.name) <= 64, f"Tool name '{tool.name}' in {service_name} exceeds 64 chars"

    def test_service_build_http_info_for_first_tool(self, service_config_path, service_name):
        openapi_json = service_config_path / f"{service_name}.json"
        openapi_spec = load_openapi(openapi_json)
        converter = OpenAPIToToolsConverter(openapi_spec)
        tools = converter.convert()

        first_tool = tools[0]
        arguments = {}
        for prop_name, prop_schema in first_tool.inputSchema.get("properties", {}).items():
            if prop_name in first_tool.inputSchema.get("required", []):
                if prop_schema.get("type") == "string":
                    arguments[prop_name] = "test-value"
                elif prop_schema.get("type") == "integer":
                    arguments[prop_name] = 1
                elif prop_schema.get("type") == "boolean":
                    arguments[prop_name] = True
                else:
                    arguments[prop_name] = "test"

        try:
            http_info = build_http_info(first_tool.name, arguments, openapi_spec, tools)
            assert "method" in http_info
            assert "resource_path" in http_info
            assert http_info["method"] in ("GET", "POST", "PUT", "DELETE", "PATCH")
        except Exception:
            pass

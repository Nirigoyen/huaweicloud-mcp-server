from unittest.mock import MagicMock

import pytest
import yaml

from assets.utils.server import MCPServer
from mcp.types import Tool


class TestMCPServerInit:
    def test_initializes_with_valid_config(self, service_config_dir):
        config_path = service_config_dir / "config.yaml"
        server = MCPServer(config_path)
        assert server.initialized is True
        assert server.config is not None
        assert server.server is not None
        assert len(server.tools) > 0

    def test_initializes_with_tools(self, service_config_dir):
        config_path = service_config_dir / "config.yaml"
        server = MCPServer(config_path)
        for tool in server.tools:
            assert isinstance(tool, Tool)
            assert tool.name
            assert tool.description

    def test_does_not_reinitialize(self, service_config_dir):
        config_path = service_config_dir / "config.yaml"
        server = MCPServer(config_path)
        server.initialize()
        assert server.initialized is True

    def test_missing_config_raises(self, tmp_path):
        with pytest.raises(Exception):
            MCPServer(tmp_path / "missing.yaml")

    def test_missing_openapi_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"service_code": "nonexistent", "transport": "http", "port": 8888}, f)
        with pytest.raises(Exception):
            MCPServer(config_file)


class TestMCPServerConfig:
    def test_config_has_service_code(self, service_config_dir):
        config_path = service_config_dir / "config.yaml"
        server = MCPServer(config_path)
        assert server.config.service_code == "ecs"

    def test_config_has_transport(self, service_config_dir):
        config_path = service_config_dir / "config.yaml"
        server = MCPServer(config_path)
        assert server.config.transport in ("http", "sse", "stdio")

    def test_config_has_port(self, service_config_dir):
        config_path = service_config_dir / "config.yaml"
        server = MCPServer(config_path)
        assert isinstance(server.config.port, int)


class TestMCPServerToolRegistration:
    def test_list_tools_returns_tools(self, service_config_dir):
        config_path = service_config_dir / "config.yaml"
        server = MCPServer(config_path)
        assert len(server.tools) > 0

    def test_tools_have_input_schema(self, service_config_dir):
        config_path = service_config_dir / "config.yaml"
        server = MCPServer(config_path)
        for tool in server.tools:
            assert "type" in tool.inputSchema
            assert tool.inputSchema["type"] == "object"
            assert "properties" in tool.inputSchema

    def test_openapi_dict_loaded(self, service_config_dir):
        config_path = service_config_dir / "config.yaml"
        server = MCPServer(config_path)
        assert "info" in server.openapi_dict
        assert "paths" in server.openapi_dict
        assert "x-host" in server.openapi_dict["info"]


class TestMCPServerClientManagement:
    @pytest.mark.asyncio
    async def test_register_client(self, service_config_dir):
        config_path = service_config_dir / "config.yaml"
        server = MCPServer(config_path)
        mock_request = MagicMock()
        await server.register_client("client-1", mock_request)
        assert "client-1" in server.active_clients

    @pytest.mark.asyncio
    async def test_unregister_client(self, service_config_dir):
        config_path = service_config_dir / "config.yaml"
        server = MCPServer(config_path)
        mock_request = MagicMock()
        await server.register_client("client-1", mock_request)
        await server.unregister_client("client-1")
        assert "client-1" not in server.active_clients

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_client(self, service_config_dir):
        config_path = service_config_dir / "config.yaml"
        server = MCPServer(config_path)
        await server.unregister_client("nonexistent")

    @pytest.mark.asyncio
    async def test_register_multiple_clients(self, service_config_dir):
        config_path = service_config_dir / "config.yaml"
        server = MCPServer(config_path)
        for i in range(5):
            await server.register_client(f"client-{i}", MagicMock())
        assert len(server.active_clients) == 5


class TestMCPServerEnsureInitialized:
    def test_ensure_initialized_raises_when_not_initialized(self, service_config_dir):
        config_path = service_config_dir / "config.yaml"
        server = MCPServer(config_path)
        server.initialized = False
        with pytest.raises(RuntimeError, match="未初始化"):
            server._ensure_initialized()

    def test_ensure_initialized_ok_when_initialized(self, service_config_dir):
        config_path = service_config_dir / "config.yaml"
        server = MCPServer(config_path)
        server._ensure_initialized()

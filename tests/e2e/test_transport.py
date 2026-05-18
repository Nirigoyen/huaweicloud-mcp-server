import json
from pathlib import Path


from assets.utils.server import MCPServer


PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestStdioTransport:
    def test_server_can_be_created_for_stdio(self, tmp_path):
        import yaml

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(
                {"service_code": "ecs", "transport": "stdio", "port": 0},
                f,
            )

        openapi_file = tmp_path / "ecs.json"
        minimal_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "ECS",
                "version": "1.0.0",
                "x-host": "ecs.{region}.myhuaweicloud.com",
            },
            "servers": [{"url": "/"}],
            "paths": {
                "/list_servers": {
                    "x-method": "GET",
                    "x-url": "{endpoint}/v1/servers",
                    "get": {
                        "operationId": "list_servers",
                        "description": "List servers",
                        "parameters": [],
                    },
                },
            },
        }
        with open(openapi_file, "w") as f:
            json.dump(minimal_spec, f)

        server = MCPServer(config_file)
        assert server.initialized is True
        assert server.config.transport == "stdio"

    def test_server_has_initialization_options(self, tmp_path):
        import yaml

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(
                {"service_code": "ecs", "transport": "stdio", "port": 0},
                f,
            )

        openapi_file = tmp_path / "ecs.json"
        minimal_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "ECS",
                "version": "1.0.0",
                "x-host": "ecs.{region}.myhuaweicloud.com",
            },
            "servers": [{"url": "/"}],
            "paths": {
                "/list_servers": {
                    "x-method": "GET",
                    "x-url": "{endpoint}/v1/servers",
                    "get": {
                        "operationId": "list_servers",
                        "description": "List servers",
                        "parameters": [],
                    },
                },
            },
        }
        with open(openapi_file, "w") as f:
            json.dump(minimal_spec, f)

        server = MCPServer(config_file)
        init_options = server.server.create_initialization_options()
        assert init_options is not None


class TestHTTPTransport:
    def test_server_can_be_created_for_http(self, tmp_path):
        import yaml

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(
                {"service_code": "ecs", "transport": "http", "port": 8888},
                f,
            )

        openapi_file = tmp_path / "ecs.json"
        minimal_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "ECS",
                "version": "1.0.0",
                "x-host": "ecs.{region}.myhuaweicloud.com",
            },
            "servers": [{"url": "/"}],
            "paths": {
                "/list_servers": {
                    "x-method": "GET",
                    "x-url": "{endpoint}/v1/servers",
                    "get": {
                        "operationId": "list_servers",
                        "description": "List servers",
                        "parameters": [],
                    },
                },
            },
        }
        with open(openapi_file, "w") as f:
            json.dump(minimal_spec, f)

        server = MCPServer(config_file)
        assert server.config.transport == "http"
        assert server.config.port == 8888


class TestSSETransport:
    def test_server_can_be_created_for_sse(self, tmp_path):
        import yaml

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(
                {"service_code": "ecs", "transport": "sse", "port": 8888},
                f,
            )

        openapi_file = tmp_path / "ecs.json"
        minimal_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "ECS",
                "version": "1.0.0",
                "x-host": "ecs.{region}.myhuaweicloud.com",
            },
            "servers": [{"url": "/"}],
            "paths": {
                "/list_servers": {
                    "x-method": "GET",
                    "x-url": "{endpoint}/v1/servers",
                    "get": {
                        "operationId": "list_servers",
                        "description": "List servers",
                        "parameters": [],
                    },
                },
            },
        }
        with open(openapi_file, "w") as f:
            json.dump(minimal_spec, f)

        server = MCPServer(config_file)
        assert server.config.transport == "sse"

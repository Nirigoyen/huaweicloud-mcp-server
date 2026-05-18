import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from assets.utils.model import MCPConfig  # noqa: E402
from assets.utils.variable import HUAWEI_ACCESS_KEY, HUAWEI_SECRET_KEY  # noqa: E402


MINIMAL_OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "TestService",
        "version": "1.0.0",
        "x-host": "test.{region}.myhuaweicloud.com",
    },
    "servers": [{"url": "/"}],
    "paths": {
        "/list_servers": {
            "x-method": "GET",
            "x-url": "{endpoint}/v1/{project_id}/servers",
            "get": {
                "operationId": "list_servers",
                "description": "List all servers",
                "parameters": [
                    {
                        "name": "project_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "description": "Project ID"},
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer", "description": "Limit"},
                    },
                ],
            },
        },
        "/create_server": {
            "x-method": "POST",
            "x-url": "{endpoint}/v1/{project_id}/servers",
            "post": {
                "operationId": "create_server",
                "description": "Create a server",
                "parameters": [
                    {
                        "name": "project_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "description": "Project ID"},
                    },
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Server name"},
                                    "flavorRef": {"type": "string", "description": "Flavor reference"},
                                },
                                "required": ["name", "flavorRef"],
                            }
                        }
                    }
                },
            },
        },
        "/delete_server": {
            "x-method": "DELETE",
            "x-url": "{endpoint}/v1/{project_id}/servers/{server_id}",
            "delete": {
                "operationId": "delete_server",
                "description": "Delete a server",
                "parameters": [
                    {
                        "name": "project_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "description": "Project ID"},
                    },
                    {
                        "name": "server_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "description": "Server ID"},
                    },
                ],
            },
        },
    },
}


OPENAPI_WITH_REFS = {
    "openapi": "3.0.0",
    "info": {
        "title": "RefTestService",
        "version": "1.0.0",
        "x-host": "ref.{region}.myhuaweicloud.com",
    },
    "servers": [{"url": "/"}],
    "components": {
        "parameters": {
            "project_id": {
                "name": "project_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string", "description": "Project ID"},
            }
        }
    },
    "paths": {
        "/list_items": {
            "x-method": "GET",
            "x-url": "{endpoint}/v1/{project_id}/items",
            "get": {
                "operationId": "list_items",
                "description": "List items",
                "parameters": [
                    {"$ref": "#/components/parameters/project_id"}
                ],
            },
        },
    },
}


OPENAPI_WITH_CIRCULAR_REF = {
    "openapi": "3.0.0",
    "info": {
        "title": "CircularRefService",
        "version": "1.0.0",
        "x-host": "circular.{region}.myhuaweicloud.com",
    },
    "servers": [{"url": "/"}],
    "components": {
        "schemas": {
            "Node": {
                "type": "object",
                "properties": {
                    "child": {"$ref": "#/components/schemas/Node"},
                    "name": {"type": "string"},
                },
            }
        }
    },
    "paths": {
        "/get_node": {
            "x-method": "GET",
            "x-url": "{endpoint}/v1/nodes",
            "get": {
                "operationId": "get_node",
                "description": "Get a node",
                "parameters": [],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Node"}
                        }
                    }
                },
            },
        },
    },
}


@pytest.fixture
def minimal_openapi_spec():
    return MINIMAL_OPENAPI_SPEC


@pytest.fixture
def openapi_with_refs():
    return OPENAPI_WITH_REFS


@pytest.fixture
def openapi_with_circular_ref():
    return OPENAPI_WITH_CIRCULAR_REF


@pytest.fixture
def sample_config_dict():
    return {
        "service_code": "ecs",
        "transport": "http",
        "port": 8888,
    }


@pytest.fixture
def sample_config_yaml(tmp_path, sample_config_dict):
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(sample_config_dict, f)
    return config_file


@pytest.fixture
def sample_openapi_json(tmp_path, minimal_openapi_spec):
    json_file = tmp_path / "ecs.json"
    with open(json_file, "w") as f:
        json.dump(minimal_openapi_spec, f)
    return json_file


@pytest.fixture
def mcp_config():
    return MCPConfig(
        service_code="ecs",
        transport="http",
        port=8888,
        ak="test-ak",
        sk="test-sk",
    )


@pytest.fixture
def mcp_config_stdio():
    return MCPConfig(
        service_code="ecs",
        transport="stdio",
        port=0,
        ak="test-ak",
        sk="test-sk",
    )


@pytest.fixture
def mock_env_credentials(monkeypatch):
    monkeypatch.setenv(HUAWEI_ACCESS_KEY, "test-access-key")
    monkeypatch.setenv(HUAWEI_SECRET_KEY, "test-secret-key")


@pytest.fixture
def mock_env_no_credentials(monkeypatch):
    monkeypatch.delenv(HUAWEI_ACCESS_KEY, raising=False)
    monkeypatch.delenv(HUAWEI_SECRET_KEY, raising=False)


@pytest.fixture
def mock_sdk_client():
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = b'{"servers": []}'
    mock_response.json.return_value = {"servers": []}
    client.do_http_request.return_value = mock_response
    return client


@pytest.fixture
def service_config_dir(tmp_path, sample_config_dict, minimal_openapi_spec):
    service_code = sample_config_dict["service_code"]
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(sample_config_dict, f)
    json_file = tmp_path / f"{service_code}.json"
    with open(json_file, "w") as f:
        json.dump(minimal_openapi_spec, f)
    return tmp_path


SERVICES_TO_TEST = ["ecs", "vpc", "rds", "iam", "elb", "eip"]


@pytest.fixture(params=SERVICES_TO_TEST)
def service_name(request):
    return request.param


@pytest.fixture
def service_config_path(service_name):
    return (
        PROJECT_ROOT
        / "huaweicloud_services_server"
        / f"mcp_server_{service_name}"
        / "src"
        / f"mcp_server_{service_name}"
        / "config"
    )

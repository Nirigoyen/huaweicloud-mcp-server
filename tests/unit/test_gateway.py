import copy
import json
from pathlib import Path

import pytest
import yaml

from assets.utils.gateway import MCPGatewayServer, ServiceInfo, DEFAULT_REGION
from assets.utils.variable import HUAWEI_REGION


@pytest.fixture
def gateway_config_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump({"service_code": "gateway", "transport": "http", "port": 8888}, f)
    return config_file


@pytest.fixture
def mock_services_root(tmp_path, minimal_openapi_spec):
    services_root = tmp_path / "huaweicloud_services_server"
    for svc_code in ["ecs", "vpc", "rds"]:
        svc_dir = services_root / f"mcp_server_{svc_code}" / "src" / f"mcp_server_{svc_code}" / "config"
        svc_dir.mkdir(parents=True)
        with open(svc_dir / "config.yaml", "w") as f:
            yaml.dump({"service_code": svc_code, "transport": "http", "port": 8888}, f)
        spec = copy.deepcopy(minimal_openapi_spec)
        spec["info"]["title"] = f"{svc_code.upper()} Service"
        spec["info"]["x-host"] = f"{svc_code}.{{region}}.myhuaweicloud.com"
        with open(svc_dir / f"{svc_code}.json", "w") as f:
            json.dump(spec, f)
    return services_root


class TestServiceInfo:
    def test_service_info_creation(self):
        info = ServiceInfo(
            service_code="ecs",
            title="ECS Service",
            x_host="ecs.{region}.myhuaweicloud.com",
            tool_count=106,
            config_path=Path("/tmp/config.yaml"),
            openapi_path=Path("/tmp/ecs.json"),
            has_region=True,
        )
        assert info.service_code == "ecs"
        assert info.has_region is True
        assert info.tool_count == 106


class TestMCPGatewayServerInit:
    def test_gateway_initializes_with_services(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        assert gateway.initialized is True
        assert len(gateway.service_registry) == 3
        assert "ecs" in gateway.service_registry
        assert "vpc" in gateway.service_registry
        assert "rds" in gateway.service_registry

    def test_gateway_service_registry_has_metadata(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        ecs = gateway.service_registry["ecs"]
        assert ecs.title == "ECS Service"
        assert ecs.x_host == "ecs.{region}.myhuaweicloud.com"
        assert ecs.has_region is True
        assert ecs.tool_count > 0

    def test_gateway_tools_are_meta_tools(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        tools = gateway._build_gateway_tools()
        tool_names = {t.name for t in tools}
        assert tool_names == {
            "list_available_services",
            "list_service_tools",
            "call_service_tool",
            "search_tools",
        }

    def test_gateway_handles_empty_services_dir(self, gateway_config_yaml, tmp_path):
        empty_root = tmp_path / "empty_services"
        empty_root.mkdir()
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=empty_root)
        assert gateway.initialized is True
        assert len(gateway.service_registry) == 0

    def test_gateway_handles_nonexistent_services_dir(self, gateway_config_yaml, tmp_path):
        nonexistent = tmp_path / "does_not_exist"
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=nonexistent)
        assert gateway.initialized is True
        assert len(gateway.service_registry) == 0


class TestListAvailableServices:
    def test_returns_all_services(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        result = gateway._handle_list_available_services()
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert len(data) == 3
        services = {s["service"] for s in data}
        assert services == {"ecs", "vpc", "rds"}

    def test_service_info_includes_metadata(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        result = gateway._handle_list_available_services()
        data = json.loads(result[0].text)
        ecs = next(s for s in data if s["service"] == "ecs")
        assert ecs["title"] == "ECS Service"
        assert ecs["has_region"] is True
        assert ecs["tool_count"] > 0


class TestListServiceTools:
    def test_returns_tools_for_service(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        result = gateway._handle_list_service_tools({"service": "ecs"})
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "name" in data[0]
        assert "description" in data[0]
        assert "inputSchema" in data[0]

    def test_returns_tools_without_schemas(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        result = gateway._handle_list_service_tools({"service": "ecs", "include_schemas": False})
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "inputSchema" not in data[0]

    def test_returns_error_for_unknown_service(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        result = gateway._handle_list_service_tools({"service": "nonexistent"})
        data = json.loads(result[0].text)
        assert "error" in data
        assert "available_services" in data

    def test_caches_tools_after_first_load(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        gateway._handle_list_service_tools({"service": "ecs"})
        assert "ecs" in gateway._tools_cache
        assert "ecs" in gateway._openapi_cache


class TestSearchTools:
    def test_search_finds_matching_tools(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        result = gateway._handle_search_tools({"query": "server"})
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "service" in data[0]
        assert "name" in data[0]

    def test_search_limits_to_50_results(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        result = gateway._handle_search_tools({"query": "server"})
        data = json.loads(result[0].text)
        assert len(data) <= 50

    def test_search_filters_by_service(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        result = gateway._handle_search_tools({"query": "server", "service": "ecs"})
        data = json.loads(result[0].text)
        assert all(s["service"] == "ecs" for s in data)

    def test_search_requires_query(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        result = gateway._handle_search_tools({"query": ""})
        data = json.loads(result[0].text)
        assert "error" in data


class TestRegionResolution:
    def test_region_from_tool_argument(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        region = gateway._resolve_region({"region": "la-south-2"})
        assert region == "la-south-2"

    def test_region_from_config(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        gateway.config.region = "ap-southeast-1"
        region = gateway._resolve_region({})
        assert region == "ap-southeast-1"

    def test_region_from_env_var(self, gateway_config_yaml, mock_services_root, monkeypatch):
        monkeypatch.setenv(HUAWEI_REGION, "sa-brazil-1")
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        region = gateway._resolve_region({})
        assert region == "sa-brazil-1"

    def test_region_defaults_to_cn_north_4(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        region = gateway._resolve_region({})
        assert region == DEFAULT_REGION

    def test_region_priority_tool_arg_over_env(self, gateway_config_yaml, mock_services_root, monkeypatch):
        monkeypatch.setenv(HUAWEI_REGION, "sa-brazil-1")
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        region = gateway._resolve_region({"region": "la-south-2"})
        assert region == "la-south-2"

    def test_region_priority_config_over_env(self, gateway_config_yaml, mock_services_root, monkeypatch):
        monkeypatch.setenv(HUAWEI_REGION, "sa-brazil-1")
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        gateway.config.region = "ap-southeast-1"
        region = gateway._resolve_region({})
        assert region == "ap-southeast-1"


class TestCallServiceTool:
    async def test_returns_error_for_unknown_service(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        result = await gateway._handle_call_service_tool(
            {
                "service": "nonexistent",
                "tool_name": "some_tool",
                "arguments": {},
            }
        )
        data = json.loads(result[0].text)
        assert "error" in data

    async def test_returns_error_for_non_dict_arguments(self, gateway_config_yaml, mock_services_root):
        gateway = MCPGatewayServer(gateway_config_yaml, services_root=mock_services_root)
        result = await gateway._handle_call_service_tool(
            {
                "service": "ecs",
                "tool_name": "list_servers",
                "arguments": "not_a_dict",
            }
        )
        data = json.loads(result[0].text)
        assert "error" in data

import json
from unittest.mock import MagicMock, patch

import pytest
import yaml

from assets.utils.hwc_tools import (
    create_api_client,
    build_http_info,
    load_openapi,
    load_config,
    filter_parameters,
)
from assets.utils.model import MCPConfig
from assets.utils.variable import HUAWEI_ACCESS_KEY, HUAWEI_SECRET_KEY, HUAWEI_REGION, MCP_SERVER_MODE, MCP_SERVER_PORT


class TestFilterParameters:
    def test_removes_none_values(self):
        result = filter_parameters({"a": "1", "b": None, "c": "3"})
        assert result == {"a": "1", "c": "3"}

    def test_removes_empty_lists(self):
        result = filter_parameters({"a": [1, 2], "b": [], "c": "3"})
        assert result == {"a": [1, 2], "c": "3"}

    def test_keeps_empty_strings(self):
        result = filter_parameters({"a": "", "b": "val"})
        assert result == {"a": "", "b": "val"}

    def test_keeps_zero_values(self):
        result = filter_parameters({"a": 0, "b": False})
        assert result == {"a": 0, "b": False}

    def test_empty_dict_returns_empty(self):
        assert filter_parameters({}) == {}

    def test_all_none_returns_empty(self):
        assert filter_parameters({"a": None, "b": None}) == {}


class TestLoadOpenapi:
    def test_loads_valid_json(self, tmp_path, minimal_openapi_spec):
        json_file = tmp_path / "test.json"
        with open(json_file, "w") as f:
            json.dump(minimal_openapi_spec, f)
        result = load_openapi(json_file)
        assert result["info"]["title"] == "TestService"

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_openapi(tmp_path / "nonexistent.json")

    def test_invalid_json_raises(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        with open(bad_file, "w") as f:
            f.write("{invalid json")
        with pytest.raises(json.JSONDecodeError):
            load_openapi(bad_file)


class TestLoadConfig:
    def test_loads_valid_config(self, sample_config_yaml):
        config = load_config(sample_config_yaml)
        assert isinstance(config, MCPConfig)
        assert config.service_code == "ecs"
        assert config.transport == "http"
        assert config.port == 8888

    def test_env_vars_override_config(self, sample_config_yaml, monkeypatch):
        monkeypatch.setenv(HUAWEI_ACCESS_KEY, "env-ak")
        monkeypatch.setenv(HUAWEI_SECRET_KEY, "env-sk")
        config = load_config(sample_config_yaml)
        assert config.ak == "env-ak"
        assert config.sk == "env-sk"

    def test_env_mode_override(self, sample_config_yaml, monkeypatch):
        monkeypatch.setenv(MCP_SERVER_MODE, "stdio")
        config = load_config(sample_config_yaml)
        assert config.transport == "stdio"

    def test_env_port_override(self, sample_config_yaml, monkeypatch):
        monkeypatch.setenv(MCP_SERVER_PORT, "9999")
        config = load_config(sample_config_yaml)
        assert config.port == 9999

    def test_env_region_override(self, sample_config_yaml, monkeypatch):
        monkeypatch.setenv(HUAWEI_REGION, "la-south-2")
        config = load_config(sample_config_yaml)
        assert config.region == "la-south-2"

    def test_region_defaults_to_none(self, sample_config_yaml):
        config = load_config(sample_config_yaml)
        assert config.region is None

    def test_invalid_transport_raises(self, sample_config_yaml, monkeypatch):
        monkeypatch.setenv(MCP_SERVER_MODE, "invalid")
        with pytest.raises(ValueError, match="无效值"):
            load_config(sample_config_yaml)

    def test_missing_config_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "missing.yaml")

    def test_invalid_yaml_raises(self, tmp_path):
        bad_yaml = tmp_path / "bad.yaml"
        with open(bad_yaml, "w") as f:
            f.write(":\n  invalid: yaml: content: [")
        with pytest.raises(ValueError):
            load_config(bad_yaml)

    def test_empty_service_code_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"service_code": "", "transport": "http", "port": 8888}, f)
        with pytest.raises(ValueError, match="service_code"):
            load_config(config_file)

    def test_zero_port_for_http_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"service_code": "ecs", "transport": "http", "port": 0}, f)
        with pytest.raises(ValueError, match="端口"):
            load_config(config_file)

    def test_zero_port_for_sse_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"service_code": "ecs", "transport": "sse", "port": 0}, f)
        with pytest.raises(ValueError, match="端口"):
            load_config(config_file)

    def test_stdio_with_zero_port_is_valid(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"service_code": "ecs", "transport": "stdio", "port": 0}, f)
        config = load_config(config_file)
        assert config.transport == "stdio"


class TestCreateApiClient:
    @patch("assets.utils.hwc_tools.ClientBuilder")
    @patch("assets.utils.hwc_tools.BasicCredentials")
    @patch("assets.utils.hwc_tools.HttpConfig")
    @patch("assets.utils.hwc_tools.Region")
    def test_creates_client_with_region_substitution(self, mock_region, mock_http_config, mock_creds, mock_builder):
        mock_builder_instance = MagicMock()
        mock_builder.return_value = mock_builder_instance
        mock_builder_instance.with_credentials.return_value = mock_builder_instance
        mock_builder_instance.with_region.return_value = mock_builder_instance
        mock_builder_instance.build.return_value = MagicMock()

        create_api_client("ak", "sk", "ecs.{region}.myhuaweicloud.com", "cn-north-4")

        mock_creds.assert_called_once_with("ak", "sk")
        mock_builder_instance.with_credentials.assert_called_once()
        mock_builder_instance.with_region.assert_called_once()
        mock_builder_instance.build.assert_called_once()

    @patch("assets.utils.hwc_tools.ClientBuilder")
    @patch("assets.utils.hwc_tools.BasicCredentials")
    @patch("assets.utils.hwc_tools.HttpConfig")
    def test_endpoint_with_com_gets_https_prefix(self, mock_http_config, mock_creds, mock_builder):
        from huaweicloudsdkcore.region.region import Region

        mock_builder_instance = MagicMock()
        mock_builder.return_value = mock_builder_instance
        mock_builder_instance.with_credentials.return_value = mock_builder_instance
        mock_builder_instance.with_region.return_value = mock_builder_instance
        mock_builder_instance.build.return_value = MagicMock()

        create_api_client("ak", "sk", "ecs.cn-north-4.myhuaweicloud.com", "cn-north-4")

        region_call_args = mock_builder_instance.with_region.call_args
        region_arg = region_call_args[0][0]
        assert isinstance(region_arg, Region)
        assert "https://" in region_arg.endpoint

    @patch("assets.utils.hwc_tools.ClientBuilder")
    @patch("assets.utils.hwc_tools.BasicCredentials")
    @patch("assets.utils.hwc_tools.HttpConfig")
    def test_defaults_to_cn_north_4_when_region_is_none(self, mock_http_config, mock_creds, mock_builder):
        from huaweicloudsdkcore.region.region import Region

        mock_builder_instance = MagicMock()
        mock_builder.return_value = mock_builder_instance
        mock_builder_instance.with_credentials.return_value = mock_builder_instance
        mock_builder_instance.with_region.return_value = mock_builder_instance
        mock_builder_instance.build.return_value = MagicMock()

        create_api_client("ak", "sk", "ecs.{region}.myhuaweicloud.com")

        region_call_args = mock_builder_instance.with_region.call_args
        region_arg = region_call_args[0][0]
        assert isinstance(region_arg, Region)
        assert "cn-north-4" in region_arg.endpoint
        assert region_arg.id == "cn-north-4"

    @patch("assets.utils.hwc_tools.ClientBuilder")
    @patch("assets.utils.hwc_tools.BasicCredentials")
    @patch("assets.utils.hwc_tools.HttpConfig")
    def test_uses_custom_region(self, mock_http_config, mock_creds, mock_builder):
        from huaweicloudsdkcore.region.region import Region

        mock_builder_instance = MagicMock()
        mock_builder.return_value = mock_builder_instance
        mock_builder_instance.with_credentials.return_value = mock_builder_instance
        mock_builder_instance.with_region.return_value = mock_builder_instance
        mock_builder_instance.build.return_value = MagicMock()

        create_api_client("ak", "sk", "ecs.{region}.myhuaweicloud.com", "la-south-2")

        region_call_args = mock_builder_instance.with_region.call_args
        region_arg = region_call_args[0][0]
        assert isinstance(region_arg, Region)
        assert "la-south-2" in region_arg.endpoint
        assert region_arg.id == "la-south-2"


class TestBuildHttpInfo:
    def test_builds_get_request_info(self, minimal_openapi_spec):
        from assets.utils.openapi import OpenAPIToToolsConverter

        tools = OpenAPIToToolsConverter(minimal_openapi_spec).convert()
        next(t for t in tools if t.name == "list_servers")

        arguments = {"project_id": "proj-123", "limit": 10}
        http_info = build_http_info("list_servers", arguments, minimal_openapi_spec, tools)

        assert http_info["method"] == "GET"
        assert "project_id" in http_info["path_params"]
        assert http_info["path_params"]["project_id"] == "proj-123"
        assert "limit" in http_info["query_params"]
        assert http_info["query_params"]["limit"] == 10

    def test_builds_post_request_info(self, minimal_openapi_spec):
        from assets.utils.openapi import OpenAPIToToolsConverter

        tools = OpenAPIToToolsConverter(minimal_openapi_spec).convert()

        arguments = {"project_id": "proj-123", "name": "my-server", "flavorRef": "flavor-1"}
        http_info = build_http_info("create_server", arguments, minimal_openapi_spec, tools)

        assert http_info["method"] == "POST"
        assert "name" in http_info["body"]
        assert http_info["body"]["name"] == "my-server"

    def test_builds_delete_request_info(self, minimal_openapi_spec):
        from assets.utils.openapi import OpenAPIToToolsConverter

        tools = OpenAPIToToolsConverter(minimal_openapi_spec).convert()

        arguments = {"project_id": "proj-123", "server_id": "server-456"}
        http_info = build_http_info("delete_server", arguments, minimal_openapi_spec, tools)

        assert http_info["method"] == "DELETE"
        assert http_info["path_params"]["server_id"] == "server-456"

    def test_missing_tool_raises(self, minimal_openapi_spec):
        from assets.utils.openapi import OpenAPIToToolsConverter

        tools = OpenAPIToToolsConverter(minimal_openapi_spec).convert()
        with pytest.raises(Exception, match="未找到"):
            build_http_info("nonexistent_tool", {}, minimal_openapi_spec, tools)

    def test_missing_required_param_raises(self, minimal_openapi_spec):
        from assets.utils.openapi import OpenAPIToToolsConverter

        tools = OpenAPIToToolsConverter(minimal_openapi_spec).convert()

        arguments = {"project_id": "proj-123"}
        with pytest.raises(Exception, match="必填参数"):
            build_http_info("create_server", arguments, minimal_openapi_spec, tools)

    def test_content_type_header_set(self, minimal_openapi_spec):
        from assets.utils.openapi import OpenAPIToToolsConverter

        tools = OpenAPIToToolsConverter(minimal_openapi_spec).convert()

        arguments = {"project_id": "proj-123", "limit": 10}
        http_info = build_http_info("list_servers", arguments, minimal_openapi_spec, tools)

        assert "Content-Type" in http_info["header_params"]

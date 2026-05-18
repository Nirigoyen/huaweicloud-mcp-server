import pytest

from assets.utils.model import MCPConfig, TransportType


class TestMCPConfig:
    def test_valid_config_creation(self):
        config = MCPConfig(
            service_code="ecs",
            transport="http",
            port=8888,
        )
        assert config.service_code == "ecs"
        assert config.transport == "http"
        assert config.port == 8888
        assert config.ak is None
        assert config.sk is None

    def test_config_with_credentials(self):
        config = MCPConfig(
            service_code="vpc",
            transport="stdio",
            port=0,
            ak="my-ak",
            sk="my-sk",
        )
        assert config.ak == "my-ak"
        assert config.sk == "my-sk"

    def test_check_valid_http(self):
        config = MCPConfig(service_code="ecs", transport="http", port=8888)
        config.check()

    def test_check_valid_sse(self):
        config = MCPConfig(service_code="ecs", transport="sse", port=8888)
        config.check()

    def test_check_valid_stdio(self):
        config = MCPConfig(service_code="ecs", transport="stdio", port=0)
        config.check()

    def test_check_empty_service_code_raises(self):
        config = MCPConfig(service_code="", transport="http", port=8888)
        with pytest.raises(ValueError, match="service_code"):
            config.check()

    def test_check_http_zero_port_raises(self):
        config = MCPConfig(service_code="ecs", transport="http", port=0)
        with pytest.raises(ValueError, match="端口"):
            config.check()

    def test_check_sse_zero_port_raises(self):
        config = MCPConfig(service_code="ecs", transport="sse", port=0)
        with pytest.raises(ValueError, match="端口"):
            config.check()

    def test_check_stdio_zero_port_ok(self):
        config = MCPConfig(service_code="ecs", transport="stdio", port=0)
        config.check()

    def test_transport_type_values(self):
        assert "sse" in TransportType.__args__
        assert "stdio" in TransportType.__args__
        assert "http" in TransportType.__args__

    def test_dataclass_equality(self):
        c1 = MCPConfig(service_code="ecs", transport="http", port=8888)
        c2 = MCPConfig(service_code="ecs", transport="http", port=8888)
        assert c1 == c2

    def test_dataclass_inequality(self):
        c1 = MCPConfig(service_code="ecs", transport="http", port=8888)
        c2 = MCPConfig(service_code="vpc", transport="http", port=8888)
        assert c1 != c2

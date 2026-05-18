from assets.utils.variable import (
    TRANSPORT_SSE,
    TRANSPORT_HTTP,
    HUAWEI_ACCESS_KEY,
    HUAWEI_SECRET_KEY,
    MCP_SERVER_MODE,
    MCP_SERVER_PORT,
)


class TestVariableConstants:
    def test_transport_sse(self):
        assert TRANSPORT_SSE == "sse"

    def test_transport_http(self):
        assert TRANSPORT_HTTP == "http"

    def test_huawei_access_key(self):
        assert HUAWEI_ACCESS_KEY == "HUAWEI_ACCESS_KEY"

    def test_huawei_secret_key(self):
        assert HUAWEI_SECRET_KEY == "HUAWEI_SECRET_KEY"

    def test_mcp_server_mode(self):
        assert MCP_SERVER_MODE == "MCP_SERVER_MODE"

    def test_mcp_server_port(self):
        assert MCP_SERVER_PORT == "MCP_SERVER_PORT"

import json
from pathlib import Path
from unittest.mock import MagicMock

from assets.utils.hwc_tools import CustomClient


def create_mock_sdk_response(data: dict, status_code: int = 200):
    mock_response = MagicMock()
    mock_response.content = json.dumps(data).encode("utf-8")
    mock_response.json.return_value = data
    mock_response.status_code = status_code
    return mock_response


def create_mock_client(response_data: dict = None):
    if response_data is None:
        response_data = {}

    client = MagicMock(spec=CustomClient)
    mock_response = create_mock_sdk_response(response_data)
    client.do_http_request.return_value = mock_response
    return client


def get_service_config_path(service_name: str) -> Path:
    return (
        Path(__file__).parent.parent.parent
        / "huaweicloud_services_server"
        / f"mcp_server_{service_name}"
        / "src"
        / f"mcp_server_{service_name}"
        / "config"
    )


def load_service_openapi(service_name: str) -> dict:
    config_path = get_service_config_path(service_name)
    json_file = config_path / f"{service_name}.json"
    with open(json_file, "r", encoding="utf-8") as f:
        return json.load(f)


def count_tools_for_service(service_name: str) -> int:
    from assets.utils.openapi import OpenAPIToToolsConverter

    openapi_spec = load_service_openapi(service_name)
    converter = OpenAPIToToolsConverter(openapi_spec)
    tools = converter.convert()
    return len(tools)

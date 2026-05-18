

from assets.utils.openapi import SwaggerRefResolver, OpenAPIToToolsConverter
from mcp.types import Tool


class TestSwaggerRefResolver:
    def test_no_refs_returns_same_structure(self, minimal_openapi_spec):
        resolver = SwaggerRefResolver(minimal_openapi_spec)
        result = resolver.parse()
        assert result["info"]["title"] == "TestService"
        assert "paths" in result

    def test_resolves_internal_refs(self, openapi_with_refs):
        resolver = SwaggerRefResolver(openapi_with_refs)
        result = resolver.parse()
        params = result["paths"]["/list_items"]["get"]["parameters"]
        assert len(params) >= 1
        resolved_param = params[0]
        assert resolved_param.get("name") == "project_id"
        assert resolved_param.get("in") == "path"

    def test_circular_ref_detection(self, openapi_with_circular_ref):
        resolver = SwaggerRefResolver(openapi_with_circular_ref)
        result = resolver.parse()
        assert result is not None
        assert "paths" in result

    def test_invalid_ref_type_returns_partial(self):
        spec = {
            "paths": {
                "/test": {
                    "get": {
                        "parameters": [{"$ref": 123}],
                        "operationId": "test_op",
                        "description": "test",
                    }
                }
            }
        }
        resolver = SwaggerRefResolver(spec)
        result = resolver.parse()
        assert result is not None

    def test_external_ref_returns_partial(self):
        spec = {
            "paths": {
                "/test": {
                    "get": {
                        "parameters": [{"$ref": "https://external.com/schema"}],
                        "operationId": "test_op",
                        "description": "test",
                    }
                }
            }
        }
        resolver = SwaggerRefResolver(spec)
        result = resolver.parse()
        assert result is not None

    def test_ref_caching(self, openapi_with_refs):
        resolver = SwaggerRefResolver(openapi_with_refs)
        result1 = resolver.parse()
        resolver2 = SwaggerRefResolver(openapi_with_refs)
        result2 = resolver2.parse()
        assert result1["info"]["title"] == result2["info"]["title"]

    def test_deeply_nested_ref(self):
        spec = {
            "components": {
                "schemas": {
                    "A": {"type": "object", "properties": {"b": {"$ref": "#/components/schemas/B"}}},
                    "B": {"type": "object", "properties": {"c": {"$ref": "#/components/schemas/C"}}},
                    "C": {"type": "object", "properties": {"value": {"type": "string"}}},
                }
            },
            "paths": {},
        }
        resolver = SwaggerRefResolver(spec)
        result = resolver.parse()
        resolved_a = result["components"]["schemas"]["A"]
        assert resolved_a["properties"]["b"]["properties"]["c"]["properties"]["value"]["type"] == "string"


class TestOpenAPIToToolsConverter:
    def test_convert_returns_tools(self, minimal_openapi_spec):
        converter = OpenAPIToToolsConverter(minimal_openapi_spec)
        tools = converter.convert()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_tools_are_mcp_tool_type(self, minimal_openapi_spec):
        converter = OpenAPIToToolsConverter(minimal_openapi_spec)
        tools = converter.convert()
        for tool in tools:
            assert isinstance(tool, Tool)
            assert tool.name
            assert tool.description
            assert isinstance(tool.inputSchema, dict)

    def test_tool_names_from_operation_id(self, minimal_openapi_spec):
        converter = OpenAPIToToolsConverter(minimal_openapi_spec)
        tools = converter.convert()
        tool_names = [t.name for t in tools]
        assert "list_servers" in tool_names
        assert "create_server" in tool_names
        assert "delete_server" in tool_names

    def test_path_parameters_in_input_schema(self, minimal_openapi_spec):
        converter = OpenAPIToToolsConverter(minimal_openapi_spec)
        tools = converter.convert()
        list_tool = next(t for t in tools if t.name == "list_servers")
        props = list_tool.inputSchema.get("properties", {})
        assert "project_id" in props
        assert props["project_id"].get("in") == "path"

    def test_query_parameters_in_input_schema(self, minimal_openapi_spec):
        converter = OpenAPIToToolsConverter(minimal_openapi_spec)
        tools = converter.convert()
        list_tool = next(t for t in tools if t.name == "list_servers")
        props = list_tool.inputSchema.get("properties", {})
        assert "limit" in props
        assert props["limit"].get("in") == "query"

    def test_request_body_properties_in_input_schema(self, minimal_openapi_spec):
        converter = OpenAPIToToolsConverter(minimal_openapi_spec)
        tools = converter.convert()
        create_tool = next(t for t in tools if t.name == "create_server")
        props = create_tool.inputSchema.get("properties", {})
        assert "name" in props
        assert "flavorRef" in props

    def test_required_parameters_populated(self, minimal_openapi_spec):
        converter = OpenAPIToToolsConverter(minimal_openapi_spec)
        tools = converter.convert()
        create_tool = next(t for t in tools if t.name == "create_server")
        required = create_tool.inputSchema.get("required", [])
        assert "project_id" in required
        assert "name" in required
        assert "flavorRef" in required

    def test_convert_with_refs(self, openapi_with_refs):
        converter = OpenAPIToToolsConverter(openapi_with_refs)
        tools = converter.convert()
        assert len(tools) >= 1
        list_tool = next(t for t in tools if t.name == "list_items")
        assert "project_id" in list_tool.inputSchema.get("properties", {})

    def test_convert_with_circular_ref_does_not_crash(self, openapi_with_circular_ref):
        converter = OpenAPIToToolsConverter(openapi_with_circular_ref)
        tools = converter.convert()
        assert isinstance(tools, list)

    def test_empty_paths_returns_empty_tools(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Empty", "version": "1.0.0"},
            "paths": {},
        }
        converter = OpenAPIToToolsConverter(spec)
        tools = converter.convert()
        assert tools == []

    def test_no_operation_id_generates_name(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/test_resource": {
                    "x-method": "GET",
                    "x-url": "{endpoint}/v1/test",
                    "get": {
                        "description": "A test operation",
                        "parameters": [],
                    },
                },
            },
        }
        converter = OpenAPIToToolsConverter(spec)
        tools = converter.convert()
        assert len(tools) == 1
        assert tools[0].name == "get_test_resource"

    def test_cleanup_name_removes_invalid_chars(self):
        assert OpenAPIToToolsConverter.cleanup_name("valid_name") == "valid_name"
        assert OpenAPIToToolsConverter.cleanup_name("some-name!") == "some_name"
        assert OpenAPIToToolsConverter.cleanup_name("-leading") == "leading"
        assert OpenAPIToToolsConverter.cleanup_name("trailing-") == "trailing"

    def test_cleanup_name_truncates_long_names(self):
        long_name = "a" * 100
        result = OpenAPIToToolsConverter.cleanup_name(long_name)
        assert len(result) <= 64

    def test_cleanup_name_empty_returns_unnamed(self):
        assert OpenAPIToToolsConverter.cleanup_name("---") == "unnamed_tool"
        assert OpenAPIToToolsConverter.cleanup_name("") == "unnamed_tool"

    def test_description_fallback_to_summary(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "x-method": "GET",
                    "x-url": "{endpoint}/v1/test",
                    "get": {
                        "operationId": "test_op",
                        "summary": "Summary fallback",
                        "parameters": [],
                    },
                },
            },
        }
        converter = OpenAPIToToolsConverter(spec)
        tools = converter.convert()
        assert tools[0].description == "Summary fallback"

    def test_multiple_methods_same_path(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/resource": {
                    "x-method": "GET",
                    "x-url": "{endpoint}/v1/resource",
                    "get": {
                        "operationId": "get_resource",
                        "description": "Get resource",
                        "parameters": [],
                    },
                    "post": {
                        "operationId": "create_resource",
                        "description": "Create resource",
                        "parameters": [],
                    },
                },
            },
        }
        converter = OpenAPIToToolsConverter(spec)
        tools = converter.convert()
        tool_names = [t.name for t in tools]
        assert "get_resource" in tool_names
        assert "create_resource" in tool_names

import asyncio
from pathlib import Path

from assets.utils.gateway import MCPGatewayServer
import argparse


def main():
    config_folder = Path(__file__).parent / "config"
    config_file = "config.yaml"

    parser = argparse.ArgumentParser(description="MCP Gateway Server")
    parser.add_argument("-p", "--port", type=int, help="Port number")
    parser.add_argument(
        "-t",
        "--transport",
        type=str,
        choices=["http", "sse", "stdio"],
        help="Transport of MCP Server",
    )
    args = parser.parse_args()

    mcp_server = MCPGatewayServer(config_folder / config_file)

    if args.transport:
        mcp_server.config.transport = args.transport
    if args.port:
        mcp_server.config.port = args.port

    asyncio.run(mcp_server.run_server())


if __name__ == "__main__":
    main()

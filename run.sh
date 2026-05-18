#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v uv &>/dev/null; then
    echo "uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source "$HOME/.local/bin/env"
fi

if [ -z "${HUAWEI_ACCESS_KEY:-}" ] || [ -z "${HUAWEI_SECRET_KEY:-}" ]; then
    echo "WARNING: HUAWEI_ACCESS_KEY and/or HUAWEI_SECRET_KEY not set."
    echo "The server will start but tool calls will fail without credentials."
    echo ""
    echo "Export them before running:"
    echo "  export HUAWEI_ACCESS_KEY='your-access-key'"
    echo "  export HUAWEI_SECRET_KEY='your-secret-key'"
    echo ""
fi

SERVICE="${1:-ecs}"
TRANSPORT="${2:-http}"
PORT="${3:-8888}"

echo "Starting Huawei Cloud MCP Server: service=$SERVICE transport=$TRANSPORT port=$PORT"
echo ""

uv run "mcp-server-$SERVICE" -t "$TRANSPORT" -p "$PORT"

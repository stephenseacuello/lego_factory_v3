# Claude Desktop Configuration for LEGO MCP Server

This directory contains example configurations for connecting Claude Desktop to the LEGO MCP Server.

## Configuration File Location

| OS | Config File Path |
|----|------------------|
| **macOS** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Windows** | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Linux** | `~/.config/claude/claude_desktop_config.json` |

## Configuration Options

### Option 1: Run MCP Server Directly (Recommended)

This runs the MCP server as a Python process. Simplest setup.

```json
{
  "mcpServers": {
    "lego-brick-maker": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/absolute/path/to/lego-mcp-fusion360/mcp-server",
      "env": {
        "FUSION_API_URL": "http://localhost:8765",
        "SLICER_API_URL": "http://localhost:8766"
      }
    }
  }
}
```

### Option 2: Using Virtual Environment

If you installed dependencies in a virtual environment:

```json
{
  "mcpServers": {
    "lego-brick-maker": {
      "command": "/absolute/path/to/lego-mcp-fusion360/mcp-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/absolute/path/to/lego-mcp-fusion360/mcp-server",
      "env": {
        "FUSION_API_URL": "http://localhost:8765",
        "SLICER_API_URL": "http://localhost:8766"
      }
    }
  }
}
```

### Option 3: Using Docker (Advanced)

Run the MCP server inside Docker:

```json
{
  "mcpServers": {
    "lego-brick-maker": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--network", "host",
        "-v", "/absolute/path/to/output:/output",
        "lego-mcp-server"
      ]
    }
  }
}
```

## Windows-Specific Configuration

On Windows, use forward slashes or escaped backslashes:

```json
{
  "mcpServers": {
    "lego-brick-maker": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "C:/Users/YourName/lego-mcp-fusion360/mcp-server",
      "env": {
        "FUSION_API_URL": "http://localhost:8765",
        "SLICER_API_URL": "http://localhost:8766"
      }
    }
  }
}
```

Or with `py` launcher:

```json
{
  "mcpServers": {
    "lego-brick-maker": {
      "command": "py",
      "args": ["-3", "-m", "src.server"],
      "cwd": "C:/Users/YourName/lego-mcp-fusion360/mcp-server",
      "env": {
        "FUSION_API_URL": "http://localhost:8765",
        "SLICER_API_URL": "http://localhost:8766"
      }
    }
  }
}
```

## After Configuration

1. **Save the config file**
2. **Restart Claude Desktop completely** (quit and reopen)
3. **Verify connection**: Ask Claude "What tools do you have for creating LEGO bricks?"

## Troubleshooting

### "Server not found" or "Failed to connect"

1. Check the `cwd` path is correct and absolute
2. Verify Python is in your PATH: `python --version`
3. Check dependencies are installed: `pip list | grep mcp`

### "Fusion 360 connection failed"

1. Ensure Fusion 360 is running
2. Verify the LegoMCP add-in is active (Tools → Add-Ins)
3. Test the API: `curl http://localhost:8765/health`

### "Slicer service unavailable"

1. Start Docker services: `docker-compose up -d`
2. Check container status: `docker-compose ps`
3. Test the API: `curl http://localhost:8766/health`

### View MCP Server Logs

Claude Desktop logs MCP server output. Check:
- **macOS**: `~/Library/Logs/Claude/`
- **Windows**: `%APPDATA%\Claude\logs\`
- **Linux**: `~/.local/share/claude/logs/`

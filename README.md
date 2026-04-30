# auto-mcp-server

Turn any Python function into an MCP tool — no boilerplate, no framework knowledge required.

You write the function. `auto-mcp-server` handles the server.

---

## The problem

Building an MCP server means learning a framework, wiring up transports, registering tools, handling schemas, and running a process. That's a lot of setup before Claude can even call your first function.

## The solution

Describe your server in a JSON file. Point it at your Python functions. Run one command.

```bash
auto-mcp-server start --config-file ./my-server.json
```

That's it. Your functions are now MCP tools, available over HTTP, ready for Claude or any MCP client to call.

---

## Quick start

**1. Install**

```bash
pip install auto-mcp-server
```

**2. Write your function**

```python
# tools/weather.py

async def get_temperature(city: str, unit: str = "celsius") -> str:
    """Get the current temperature for a city."""
    # your actual logic here
    return f"The temperature in {city} is 22°{unit[0].upper()}"
```

**3. Create a config file**

```json
{
  "name": "weather-server",
  "version": "1.0.0",
  "host": "127.0.0.1",
  "port": 8000,
  "transport": "http",
  "tools": [
    {
      "file": "./tools/weather.py",
      "function": "get_temperature"
    }
  ]
}
```

**4. Start the server**

```bash
auto-mcp-server start --config-file ./server.json
```

```
Starting 'weather-server' on http://127.0.0.1:8000 with 1 tool(s)...
```

---

## Config reference

### Server fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | string | **required** | Name of the MCP server |
| `version` | string | `"1.0.0"` | Server version |
| `host` | string | `"127.0.0.1"` | Host to bind to |
| `port` | int | `8000` | Port to listen on |
| `transport` | string | `"http"` | Transport protocol: `http`, `sse`, or `streamable-http` |
| `tools` | array | **required** | List of tool definitions |

### Tool fields

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | string | yes | Path to the `.py` file (relative to the config file or absolute) |
| `function` | string | yes | Name of the function to expose as a tool |
| `name` | string | no | Override the tool name (defaults to the function name) |
| `description` | string | no | Override the tool description (defaults to the function's docstring) |

### Paths are relative to the config file

`file` paths are resolved relative to where the JSON lives, not where you run the command from. This means configs are portable — you can move the whole directory and it still works.

---

## CLI

### `validate` — check without starting

```bash
auto-mcp-server validate --config-file ./server.json
```

Runs all checks and exits. Use this in CI or before deploying.

### `start` — validate and run

```bash
auto-mcp-server start --config-file ./server.json
auto-mcp-server start --config-file ./server.json --host 0.0.0.0 --port 9000
```

`--host` and `--port` override whatever is in the config file.

---

## Validation

Before starting (or when running `validate`), `auto-mcp-server` checks:

- **JSON is valid** and all required fields are present
- **Each `file` exists** and is a `.py` file
- **Each file imports cleanly** — syntax errors and import errors are caught and reported
- **Each `function` exists** in its file and is callable
- **Type hints are present** — a warning (not an error) if parameters lack type annotations, since they help MCP clients understand what to pass

Errors are reported clearly and the server won't start if any check fails:

```
Validation failed:
  ERROR: Tool[0] 'get_temperature': file not found: /path/to/tools/weather.py
  ERROR: Tool[1] 'process_data': function 'process_data' not found in utils.py
```

---

## Writing tools

### Use type hints

Type hints are how `auto-mcp-server` (via FastMCP) generates the input schema for each tool. Always annotate your parameters:

```python
# Good — Claude knows exactly what to pass
async def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    ...

# Bad — no schema can be inferred
async def convert_currency(amount, from_currency, to_currency):
    ...
```

### Use docstrings

The function's docstring becomes the tool description that Claude reads to decide when to call it. Write it clearly:

```python
async def search_products(query: str, max_results: int = 10) -> str:
    """Search the product catalog and return matching items with prices and availability."""
    ...
```

### Sync and async both work

```python
# async
async def fetch_data(url: str) -> str:
    ...

# sync also works
def calculate_total(items: list[float]) -> float:
    ...
```

### One file, many tools

A single Python file can contain multiple functions. Register each one separately in the config:

```json
{
  "tools": [
    { "file": "./tools/math.py", "function": "add" },
    { "file": "./tools/math.py", "function": "multiply" },
    { "file": "./tools/math.py", "function": "factorial" }
  ]
}
```

---

## Multiple tools, multiple files

```json
{
  "name": "my-api-server",
  "version": "2.0.0",
  "host": "0.0.0.0",
  "port": 8080,
  "transport": "http",
  "tools": [
    {
      "file": "./tools/database.py",
      "function": "query_users",
      "description": "Query the users table with optional filters"
    },
    {
      "file": "./tools/email.py",
      "function": "send_notification",
      "name": "notify_user"
    },
    {
      "file": "./tools/reports.py",
      "function": "generate_summary"
    }
  ]
}
```

---

## Requirements

- Python 3.10+
- Dependencies installed automatically: `fastmcp`, `pydantic`, `click`

---

## License

MIT

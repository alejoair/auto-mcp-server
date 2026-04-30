## Documentation Index
Fetch the complete documentation index at: https://code.claude.com/docs/llms.txt
Use this file to discover all available pages before exploring further.

# Give Claude custom tools

> Define custom tools with the Claude Agent SDK's in-process MCP server so Claude can call your functions, hit your APIs, and perform domain-specific operations.

Custom tools extend the Agent SDK by letting you define your own functions that Claude can call during a conversation. Using the SDK's in-process MCP server, you can give Claude access to databases, external APIs, domain-specific logic, or any other capability your application needs.

This guide covers how to define tools with input schemas and handlers, bundle them into an MCP server, pass them to `query`, and control which tools Claude can access. It also covers error handling, tool annotations, and returning non-text content like images.

## Quick reference

| If you want to...                            | Do this                                                                                                                                                                                                       |
| :------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Define a tool                                | Use [`@tool`](/en/agent-sdk/python#tool) (Python) or [`tool()`](/en/agent-sdk/typescript#tool) (TypeScript) with a name, description, schema, and handler. See [Create a custom tool](#create-a-custom-tool). |
| Register a tool with Claude                  | Wrap in `create_sdk_mcp_server` / `createSdkMcpServer` and pass to `mcpServers` in `query()`. See [Call a custom tool](#call-a-custom-tool).                                                                  |
| Pre-approve a tool                           | Add to your allowed tools. See [Configure allowed tools](#configure-allowed-tools).                                                                                                                           |
| Remove a built-in tool from Claude's context | Pass a `tools` array listing only the built-ins you want. See [Configure allowed tools](#configure-allowed-tools).                                                                                            |
| Let Claude call tools in parallel            | Set `readOnlyHint: true` on tools with no side effects. See [Add tool annotations](#add-tool-annotations).                                                                                                    |
| Handle errors without stopping the loop      | Return `isError: true` instead of throwing. See [Handle errors](#handle-errors).                                                                                                                              |
| Return images or files                       | Use `image` or `resource` blocks in the content array. See [Return images and resources](#return-images-and-resources).                                                                                       |
| Scale to many tools                          | Use [tool search](/en/agent-sdk/tool-search) to load tools on demand.                                                                                                                                         |

## Create a custom tool

A tool is defined by four parts, passed as arguments to the [`tool()`](/en/agent-sdk/typescript#tool) helper in TypeScript or the [`@tool`](/en/agent-sdk/python#tool) decorator in Python:

* **Name:** a unique identifier Claude uses to call the tool.
* **Description:** what the tool does. Claude reads this to decide when to call it.
* **Input schema:** the arguments Claude must provide. In TypeScript this is always a [Zod schema](https://zod.dev/), and the handler's `args` are typed from it automatically. In Python this is a dict mapping names to types, like `{"latitude": float}`, which the SDK converts to JSON Schema for you. The Python decorator also accepts a full [JSON Schema](https://json-schema.org/understanding-json-schema/about) dict directly when you need enums, ranges, optional fields, or nested objects.
* **Handler:** the async function that runs when Claude calls the tool. It receives the validated arguments and must return an object with:
  * `content` (required): an array of result blocks, each with a `type` of `"text"`, `"image"`, or `"resource"`. See [Return images and resources](#return-images-and-resources) for non-text blocks.
  * `isError` (optional): set to `true` to signal a tool failure so Claude can react to it. See [Handle errors](#handle-errors).

After defining a tool, wrap it in a server with [`createSdkMcpServer`](/en/agent-sdk/typescript#create-sdk-mcp-server) (TypeScript) or [`create_sdk_mcp_server`](/en/agent-sdk/python#create-sdk-mcp-server) (Python). The server runs in-process inside your application, not as a separate process.

### Weather tool example

This example defines a `get_temperature` tool and wraps it in an MCP server. It only sets up the tool; to pass it to `query` and run it, see [Call a custom tool](#call-a-custom-tool) below.

```python
from typing import Any
import httpx
from claude_agent_sdk import tool, create_sdk_mcp_server


# Define a tool: name, description, input schema, handler
@tool(
    "get_temperature",
    "Get the current temperature at a location",
    {"latitude": float, "longitude": float},
)
async def get_temperature(args: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": args["latitude"],
                "longitude": args["longitude"],
                "current": "temperature_2m",
                "temperature_unit": "fahrenheit",
            },
        )
        data = response.json()

    # Return a content array - Claude sees this as the tool result
    return {
        "content": [
            {
                "type": "text",
                "text": f"Temperature: {data['current']['temperature_2m']}°F",
            }
        ]
    }


# Wrap the tool in an in-process MCP server
weather_server = create_sdk_mcp_server(
    name="weather",
    version="1.0.0",
    tools=[get_temperature],
)
```

```typescript
import { tool, createSdkMcpServer } from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";

// Define a tool: name, description, input schema, handler
const getTemperature = tool(
  "get_temperature",
  "Get the current temperature at a location",
  {
    latitude: z.number().describe("Latitude coordinate"),
    longitude: z.number().describe("Longitude coordinate")
  },
  async (args) => {
    const response = await fetch(
      `https://api.open-meteo.com/v1/forecast?latitude=${args.latitude}&longitude=${args.longitude}&current=temperature_2m&temperature_unit=fahrenheit`
    );
    const data: any = await response.json();

    // Return a content array - Claude sees this as the tool result
    return {
      content: [{ type: "text", text: `Temperature: ${data.current.temperature_2m}°F` }]
    };
  }
);

// Wrap the tool in an in-process MCP server
const weatherServer = createSdkMcpServer({
  name: "weather",
  version: "1.0.0",
  tools: [getTemperature]
});
```

See the [`tool()`](/en/agent-sdk/typescript#tool) TypeScript reference or the [`@tool`](/en/agent-sdk/python#tool) Python reference for full parameter details, including JSON Schema input formats and return value structure.

> **Tip:** To make a parameter optional: in TypeScript, add `.default()` to the Zod field. In Python, the dict schema treats every key as required, so leave the parameter out of the schema, mention it in the description string, and read it with `args.get()` in the handler. The [`get_precipitation_chance` tool below](#add-more-tools) shows both patterns.

### Call a custom tool

Pass the MCP server you created to `query` via the `mcpServers` option. The key in `mcpServers` becomes the `{server_name}` segment in each tool's fully qualified name: `mcp__{server_name}__{tool_name}`. List that name in `allowedTools` so the tool runs without a permission prompt.

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage


async def main():
    options = ClaudeAgentOptions(
        mcp_servers={"weather": weather_server},
        allowed_tools=["mcp__weather__get_temperature"],
    )

    async for message in query(
        prompt="What's the temperature in San Francisco?",
        options=options,
    ):
        if isinstance(message, ResultMessage) and message.subtype == "success":
            print(message.result)


asyncio.run(main())
```

```typescript
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "What's the temperature in San Francisco?",
  options: {
    mcpServers: { weather: weatherServer },
    allowedTools: ["mcp__weather__get_temperature"]
  }
})) {
  if (message.type === "result" && message.subtype === "success") {
    console.log(message.result);
  }
}
```

### Add more tools

A server holds as many tools as you list in its `tools` array. With more than one tool on a server, you can list each one in `allowedTools` individually or use the wildcard `mcp__weather__*` to cover every tool the server exposes.

```python
@tool(
    "get_precipitation_chance",
    "Get the hourly precipitation probability for a location. "
    "Optionally pass 'hours' (1-24) to control how many hours to return.",
    {"latitude": float, "longitude": float},
)
async def get_precipitation_chance(args: dict[str, Any]) -> dict[str, Any]:
    hours = args.get("hours", 12)
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": args["latitude"],
                "longitude": args["longitude"],
                "hourly": "precipitation_probability",
                "forecast_days": 1,
            },
        )
        data = response.json()
    chances = data["hourly"]["precipitation_probability"][:hours]

    return {
        "content": [
            {
                "type": "text",
                "text": f"Next {hours} hours: {'%, '.join(map(str, chances))}%",
            }
        ]
    }


weather_server = create_sdk_mcp_server(
    name="weather",
    version="1.0.0",
    tools=[get_temperature, get_precipitation_chance],
)
```

```typescript
const getPrecipitationChance = tool(
  "get_precipitation_chance",
  "Get the hourly precipitation probability for a location",
  {
    latitude: z.number(),
    longitude: z.number(),
    hours: z.number().int().min(1).max(24).default(12).describe("How many hours of forecast to return")
  },
  async (args) => {
    const response = await fetch(
      `https://api.open-meteo.com/v1/forecast?latitude=${args.latitude}&longitude=${args.longitude}&hourly=precipitation_probability&forecast_days=1`
    );
    const data: any = await response.json();
    const chances = data.hourly.precipitation_probability.slice(0, args.hours);

    return {
      content: [{ type: "text", text: `Next ${args.hours} hours: ${chances.join("%, ")}%` }]
    };
  }
);

const weatherServer = createSdkMcpServer({
  name: "weather",
  version: "1.0.0",
  tools: [getTemperature, getPrecipitationChance]
});
```

### Add tool annotations

[Tool annotations](https://modelcontextprotocol.io/docs/concepts/tools#tool-annotations) are optional metadata describing how a tool behaves. Pass them as the fifth argument to `tool()` helper in TypeScript or via the `annotations` keyword argument for the `@tool` decorator in Python.

| Field             | Default | Meaning                                                                                                               |
| :---------------- | :------ | :-------------------------------------------------------------------------------------------------------------------- |
| `readOnlyHint`    | `false` | Tool does not modify its environment. Controls whether the tool can be called in parallel with other read-only tools. |
| `destructiveHint` | `true`  | Tool may perform destructive updates. Informational only.                                                             |
| `idempotentHint`  | `false` | Repeated calls with the same arguments have no additional effect. Informational only.                                 |
| `openWorldHint`   | `true`  | Tool reaches systems outside your process. Informational only.                                                        |

```python
from claude_agent_sdk import tool, ToolAnnotations


@tool(
    "get_temperature",
    "Get the current temperature at a location",
    {"latitude": float, "longitude": float},
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def get_temperature(args):
    return {"content": [{"type": "text", "text": "..."}]}
```

```typescript
tool(
  "get_temperature",
  "Get the current temperature at a location",
  { latitude: z.number(), longitude: z.number() },
  async (args) => ({ content: [{ type: "text", text: `...` }] }),
  { annotations: { readOnlyHint: true } }
);
```

## Control tool access

### Tool name format

When MCP tools are exposed to Claude, their names follow a specific format:

* Pattern: `mcp__{server_name}__{tool_name}`
* Example: A tool named `get_temperature` in server `weather` becomes `mcp__weather__get_temperature`

### Configure allowed tools

| Option                    | Layer        | Effect                                                                                                                                            |
| :------------------------ | :----------- | :------------------------------------------------------------------------------------------------------------------------------------------------ |
| `tools: ["Read", "Grep"]` | Availability | Only the listed built-ins are in Claude's context. Unlisted built-ins are removed. MCP tools are unaffected.                                      |
| `tools: []`               | Availability | All built-ins are removed. Claude can only use your MCP tools.                                                                                    |
| allowed tools             | Permission   | Listed tools run without a permission prompt. Unlisted tools remain available; calls go through the permission flow.                              |
| disallowed tools          | Permission   | Every call to a listed tool is denied. The tool stays in Claude's context, so Claude may still attempt it before the call is rejected.            |

## Handle errors

| What happens                                                                             | Result                                                                                                           |
| :--------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------- |
| Handler throws an uncaught exception                                                     | Agent loop stops. Claude never sees the error, and the `query` call fails.                                       |
| Handler catches the error and returns `isError: true` (TS) / `"is_error": True` (Python) | Agent loop continues. Claude sees the error as data and can retry, try a different tool, or explain the failure. |

```python
@tool(
    "fetch_data",
    "Fetch data from an API",
    {"endpoint": str},
)
async def fetch_data(args: dict[str, Any]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(args["endpoint"])
            if response.status_code != 200:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"API error: {response.status_code} {response.reason_phrase}",
                        }
                    ],
                    "is_error": True,
                }

            data = response.json()
            return {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Failed to fetch data: {str(e)}"}],
            "is_error": True,
        }
```

## Return images and resources

### Images

| Field      | Type      | Notes                                                                      |
| :--------- | :-------- | :------------------------------------------------------------------------- |
| `type`     | `"image"` |                                                                            |
| `data`     | `string`  | Base64-encoded bytes. Raw base64 only, no `data:image/...;base64,` prefix  |
| `mimeType` | `string`  | Required. For example `image/png`, `image/jpeg`, `image/webp`, `image/gif` |

```python
import base64
import httpx


@tool("fetch_image", "Fetch an image from a URL and return it to Claude", {"url": str})
async def fetch_image(args):
    async with httpx.AsyncClient() as client:
        response = await client.get(args["url"])

    return {
        "content": [
            {
                "type": "image",
                "data": base64.b64encode(response.content).decode("ascii"),
                "mimeType": response.headers.get("content-type", "image/png"),
            }
        ]
    }
```

### Resources

| Field               | Type         | Notes                                                       |
| :------------------ | :----------- | :---------------------------------------------------------- |
| `type`              | `"resource"` |                                                             |
| `resource.uri`      | `string`     | Identifier for the content. Any URI scheme                  |
| `resource.text`     | `string`     | The content, if it's text. Provide this or `blob`, not both |
| `resource.blob`     | `string`     | The content base64-encoded, if it's binary                  |
| `resource.mimeType` | `string`     | Optional                                                    |

```python
return {
    "content": [
        {
            "type": "resource",
            "resource": {
                "uri": "file:///tmp/report.md",
                "mimeType": "text/markdown",
                "text": "# Report\n...",
            },
        }
    ]
}
```

## Example: unit converter

```python
from typing import Any
from claude_agent_sdk import tool, create_sdk_mcp_server


@tool(
    "convert_units",
    "Convert a value from one unit to another",
    {
        "type": "object",
        "properties": {
            "unit_type": {
                "type": "string",
                "enum": ["length", "temperature", "weight"],
                "description": "Category of unit",
            },
            "from_unit": {
                "type": "string",
                "description": "Unit to convert from, e.g. kilometers, fahrenheit, pounds",
            },
            "to_unit": {"type": "string", "description": "Unit to convert to"},
            "value": {"type": "number", "description": "Value to convert"},
        },
        "required": ["unit_type", "from_unit", "to_unit", "value"],
    },
)
async def convert_units(args: dict[str, Any]) -> dict[str, Any]:
    conversions = {
        "length": {
            "kilometers_to_miles": lambda v: v * 0.621371,
            "miles_to_kilometers": lambda v: v * 1.60934,
            "meters_to_feet": lambda v: v * 3.28084,
            "feet_to_meters": lambda v: v * 0.3048,
        },
        "temperature": {
            "celsius_to_fahrenheit": lambda v: (v * 9) / 5 + 32,
            "fahrenheit_to_celsius": lambda v: (v - 32) * 5 / 9,
            "celsius_to_kelvin": lambda v: v + 273.15,
            "kelvin_to_celsius": lambda v: v - 273.15,
        },
        "weight": {
            "kilograms_to_pounds": lambda v: v * 2.20462,
            "pounds_to_kilograms": lambda v: v * 0.453592,
            "grams_to_ounces": lambda v: v * 0.035274,
            "ounces_to_grams": lambda v: v * 28.3495,
        },
    }

    key = f"{args['from_unit']}_to_{args['to_unit']}"
    fn = conversions.get(args["unit_type"], {}).get(key)

    if not fn:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Unsupported conversion: {args['from_unit']} to {args['to_unit']}",
                }
            ],
            "is_error": True,
        }

    result = fn(args["value"])
    return {
        "content": [
            {
                "type": "text",
                "text": f"{args['value']} {args['from_unit']} = {result:.4f} {args['to_unit']}",
            }
        ]
    }


converter_server = create_sdk_mcp_server(
    name="converter",
    version="1.0.0",
    tools=[convert_units],
)
```

## Next steps

* If your server grows to dozens of tools, see [tool search](/en/agent-sdk/tool-search) to defer loading them until Claude needs them.
* To connect to external MCP servers (filesystem, GitHub, Slack) instead of building your own, see [Connect MCP servers](/en/agent-sdk/mcp).
* To control which tools run automatically versus requiring approval, see [Configure permissions](/en/agent-sdk/permissions).

## Related documentation

* [TypeScript SDK Reference](/en/agent-sdk/typescript)
* [Python SDK Reference](/en/agent-sdk/python)
* [MCP Documentation](https://modelcontextprotocol.io)
* [SDK Overview](/en/agent-sdk/overview)

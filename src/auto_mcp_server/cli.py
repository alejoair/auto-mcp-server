from __future__ import annotations

import sys

import click
from pydantic import ValidationError

from .config import load_config
from .validator import validate_config


@click.group()
def main() -> None:
    """auto-mcp-server — Run MCP servers from a JSON config file."""


@main.command()
@click.option("--config-file", required=True, type=click.Path(exists=True), help="Path to the server JSON config.")
def validate(config_file: str) -> None:
    """Validate a server config without starting it."""
    try:
        config = load_config(config_file)
    except ValidationError as e:
        click.secho("Config validation failed:", fg="red", bold=True)
        for err in e.errors():
            click.secho(f"  - {' -> '.join(str(l) for l in err['loc'])}: {err['msg']}", fg="red")
        sys.exit(1)
    except Exception as e:
        click.secho(f"Failed to parse config: {e}", fg="red", bold=True)
        sys.exit(1)

    result = validate_config(config)

    for warning in result.warnings:
        click.secho(f"  WARNING: {warning}", fg="yellow")

    if not result.ok:
        click.secho("Validation failed:", fg="red", bold=True)
        for error in result.errors:
            click.secho(f"  ERROR: {error}", fg="red")
        sys.exit(1)

    click.secho(f"Config is valid. {len(config.tools)} tool(s) ready.", fg="green", bold=True)


@main.command()
@click.option("--config-file", required=True, type=click.Path(exists=True), help="Path to the server JSON config.")
@click.option("--host", default=None, help="Override host from config.")
@click.option("--port", default=None, type=int, help="Override port from config.")
def start(config_file: str, host: str | None, port: int | None) -> None:
    """Validate and start the MCP server."""
    try:
        config = load_config(config_file)
    except ValidationError as e:
        click.secho("Config validation failed:", fg="red", bold=True)
        for err in e.errors():
            click.secho(f"  - {' -> '.join(str(l) for l in err['loc'])}: {err['msg']}", fg="red")
        sys.exit(1)
    except Exception as e:
        click.secho(f"Failed to parse config: {e}", fg="red", bold=True)
        sys.exit(1)

    if host:
        config.host = host
    if port:
        config.port = port

    result = validate_config(config)

    for warning in result.warnings:
        click.secho(f"  WARNING: {warning}", fg="yellow")

    if not result.ok:
        click.secho("Validation failed — server not started:", fg="red", bold=True)
        for error in result.errors:
            click.secho(f"  ERROR: {error}", fg="red")
        sys.exit(1)

    click.secho(
        f"Starting '{config.name}' on {config.transport}://{config.host}:{config.port} "
        f"with {len(config.tools)} tool(s)...",
        fg="green",
        bold=True,
    )

    from .server import run_server
    run_server(config)

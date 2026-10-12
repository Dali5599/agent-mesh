import asyncio
import sys
from typing import Optional
import typer
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from agent_mesh.config.loader import ConfigLoader
from agent_mesh.transport.server import MeshServer
from agent_mesh.api.app import create_app
import uvicorn

app = typer.Typer(
    help="High-Performance Distributed Service Mesh for AI Agent Swarms CLI",
    add_completion=False,
)
console = Console()

@app.command("start")
def start_mesh(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind host for the mesh node"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port for the mesh node"),
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="Path to YAML configuration file"),
) -> None:
    """Start a local Agent Mesh node and its control-plane API."""
    console.print(Panel.fit(
        f"[bold cyan]Initializing Agent Mesh Node[/bold cyan]\n"
        f"Host: [green]{host}[/green] | Port: [green]{port}[/green]",
        title="🦈 Requin Coder Mesh Engine"
    ))

    try:
        if config_path:
            loader = ConfigLoader(config_path)
            config = loader.load()
            console.print(f"[dim]Loaded configuration from {config_path}[/dim]")

        uvicorn.run(
            "agent_mesh.api.app:create_app",
            host=host,
            port=port,
            factory=True,
            reload=False,
            log_level="info"
        )
    except Exception as e:
        console.print(f"[bold red]Failed to start mesh node:[/bold red] {e}")
        raise typer.Exit(code=1)

@app.command("status")
def status(
    endpoint: str = typer.Option("http://127.0.0.1:8000", "--endpoint", "-e", help="Mesh node API endpoint"),
) -> None:
    """Inspect the operational status and health of the mesh node and connected agents."""
    console.print(f"[bold]Checking mesh status at {endpoint}...[/bold]")

    try:
        response = httpx.get(f"{endpoint}/health", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            console.print("[bold green]✔ Node is Healthy and Responding[/bold green]")
            
            table = Table(title="Node Telemetry & Metrics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")
            
            for key, val in data.items():
                table.add_row(str(key), str(val))
            console.print(table)
        else:
            console.print(f"[bold red]Node returned status {response.status_code}[/bold red]")
            raise typer.Exit(code=1)
    except httpx.RequestError as exc:
        console.print(f"[bold red]Connection error:[/bold red] {exc}")
        raise typer.Exit(code=1)

@app.command("route")
def route_task(
    agent: str = typer.Option(..., "--agent", "-a", help="Target agent capability or ID"),
    payload: str = typer.Option("{}", "--payload", "-d", help="JSON payload to dispatch"),
    endpoint: str = typer.Option("http://127.0.0.1:8000", "--endpoint", "-e", help="Mesh node API endpoint"),
) -> None:
    """Test routing a task payload through the mesh routing engine."""
    import json
    try:
        parsed_payload = json.loads(payload)
    except json.JSONDecodeError as e:
        console.print(f"[bold red]Invalid JSON payload:[/bold red] {e}")
        raise typer.Exit(code=1)

    console.print(f"[bold cyan]Dispatching task to agent capability: [yellow]{agent}[/yellow][/bold cyan]")

    try:
        response = httpx.post(
            f"{endpoint}/v1/route",
            json={"target_agent": agent, "payload": parsed_payload},
            timeout=30.0
        )
        if response.status_code == 200:
            res_data = response.json()
            console.print("[bold green]✔ Task successfully processed by mesh[/bold green]")
            
            syntax = Syntax(json.dumps(res_data, indent=2), "json", theme="monokai", line_numbers=True)
            console.print(syntax)
        else:
            console.print(f"[bold red]Routing failed with status {response.status_code}:[/bold red]")
            console.print(response.text)
            raise typer.Exit(code=1)
    except httpx.RequestError as exc:
        console.print(f"[bold red]Mesh communication error:[/bold red] {exc}")
        raise typer.Exit(code=1)

@app.command("nodes")
def list_nodes(
    endpoint: str = typer.Option("http://127.0.0.1:8000", "--endpoint", "-e", help="Mesh node API endpoint"),
) -> None:
    """List all registered nodes and agent swarms participating in the mesh."""
    console.print(f"[bold]Fetching registered agent nodes from {endpoint}...[/bold]")

    try:
        response = httpx.get(f"{endpoint}/v1/nodes", timeout=5.0)
        if response.status_code == 200:
            nodes = response.json()
            
            table = Table(title="Active Swarm Nodes")
            table.add_column("Node ID", style="cyan")
            table.add_column("Capabilities", style="green")
            table.add_column("Status", style="magenta")
            table.add_column("Load", style="yellow")

            for node in nodes.get("nodes", []):
                table.add_row(
                    node.get("id", "unknown"),
                    ", ".join(node.get("capabilities", [])),
                    node.get("status", "unknown"),
                    str(node.get("load", 0.0))
                )
            console.print(table)
        else:
            console.print(f"[bold red]Failed to fetch nodes, status {response.status_code}[/bold red]")
            raise typer.Exit(code=1)
    except httpx.RequestError as exc:
        console.print(f"[bold red]Connection error:[/bold red] {exc}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()

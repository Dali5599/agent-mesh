import asyncio
import json
import sys
from typing import Optional
import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich import print as rprint

app = typer.Typer(
    name="agent-mesh",
    help="High-Performance Distributed Service Mesh for AI Agent Swarms CLI.",
    add_completion=False,
)

console = Console()

DEFAULT_API_URL = "http://localhost:8000"


def get_api_client(base_url: str = DEFAULT_API_URL) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)


@app.command("nodes")
def list_nodes(
    api_url: str = typer.Option(DEFAULT_API_URL, "--api-url", "-u", help="Mesh API URL"),
) -> None:
    """
    List all active nodes registered in the mesh.
    """
    client = get_api_client(api_url)
    try:
        response = client.get("/v1/nodes")
        if response.status_code != 200:
            console.print(f"[bold red]Error fetching nodes:[/bold red] {response.text}")
            raise typer.Exit(code=1)

        data = response.json()
        nodes = data.get("nodes", [])

        table = Table(title="Registered Agent Nodes", show_header=True, header_style="bold magenta")
        table.add_column("Node ID", style="cyan", no_wrap=True)
        table.add_column("Host", style="green")
        table.add_column("Port", style="yellow")
        table.add_column("Capabilities", style="blue")
        table.add_column("Status", style="bold")

        for node in nodes:
            status = "[green]ACTIVE[/green]" if node.get("active", True) else "[red]INACTIVE[/red]"
            caps = ", ".join(node.get("capabilities", []))
            table.add_row(
                node.get("node_id", "N/A"),
                node.get("host", "N/A"),
                str(node.get("port", "N/A")),
                caps,
                status,
            )

        console.print(table)

    except httpx.RequestError as exc:
        console.print(f"[bold red]Connection error:[/bold red] Could not connect to API at {api_url}. Details: {exc}")
        raise typer.Exit(code=1)
    finally:
        client.close()


@app.command("dispatch")
def dispatch_task(
    agent_id: str = typer.Option(..., "--agent-id", "-a", help="Target agent capability or ID"),
    payload: str = typer.Option("{}", "--payload", "-p", help="JSON payload for the task"),
    api_url: str = typer.Option(DEFAULT_API_URL, "--api-url", "-u", help="Mesh API URL"),
) -> None:
    """
    Dispatch a task to an agent through the mesh routing engine.
    """
    client = get_api_client(api_url)
    try:
        try:
            parsed_payload = json.loads(payload)
        except json.JSONDecodeError as jde:
            console.print(f"[bold red]Invalid JSON payload:[/bold red] {jde}")
            raise typer.Exit(code=1)

        task_data = {
            "agent_id": agent_id,
            "payload": parsed_payload,
        }

        console.print(f"[bold cyan]Dispatching task to target:[/bold cyan] {agent_id}...")
        response = client.post("/v1/tasks/dispatch", json=task_data)

        if response.status_code != 200:
            console.print(f"[bold red]Task dispatch failed:[/bold red] {response.text}")
            raise typer.Exit(code=1)

        result = response.json()
        formatted_json = json.dumps(result, indent=2)
        syntax = Syntax(formatted_json, "json", theme="monokai", line_numbers=True)

        console.print(Panel(syntax, title="[bold green]Task Execution Result[/bold green]", expand=False))

    except httpx.RequestError as exc:
        console.print(f"[bold red]Connection error:[/bold red] Could not connect to API at {api_url}. Details: {exc}")
        raise typer.Exit(code=1)
    finally:
        client.close()


@app.command("health")
def health_check(
    api_url: str = typer.Option(DEFAULT_API_URL, "--api-url", "-u", help="Mesh API URL"),
) -> None:
    """
    Check the overall health and status of the mesh control plane.
    """
    client = get_api_client(api_url)
    try:
        response = client.get("/health")
        if response.status_code != 200:
            console.print(f"[bold red]Mesh Unhealthy:[/bold red] Status code {response.status_code}")
            raise typer.Exit(code=1)

        data = response.json()
        console.print(Panel(
            f"[bold green]Status:[/bold green] {data.get('status', 'OK')}\n"
            f"[bold cyan]Service Mesh:[/bold cyan] agent-mesh\n"
            f"[bold yellow]Control Plane:[/bold yellow] Operational",
            title="Mesh Health Check",
            expand=False,
        ))
    except httpx.RequestError as exc:
        console.print(f"[bold red]Connection error:[/bold red] Control plane is unreachable at {api_url}. Details: {exc}")
        raise typer.Exit(code=1)
    finally:
        client.close()


if __name__ == "__main__":
    app()

import typer
import os
from pathlib import Path
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.panel import Panel

from sql_autopsy.parser import Parser
from sql_autopsy.grapher import DependencyGrapher
from sql_autopsy.instrumentor import Instrumentor
from sql_autopsy.executor import Executor
from sql_autopsy.diagnoser import Diagnoser

app = typer.Typer(help="sql-autopsy: A runtime logical debugger for SQL")
console = Console()

@app.command()
def run(
    script: Path = typer.Argument(..., help="Path to the SQL script to debug"),
    target: str = typer.Option("duckdb:///:memory:", help="Database connection string")
):
    """
    Run an autopsy on a SQL script to find logical bugs.
    """
    if not script.exists():
        console.print(f"[bold red]Error:[/] File '{script}' not found.")
        raise typer.Exit(code=1)
        
    sql = script.read_text(encoding="utf-8")
    
    with console.status("[bold green]Parsing SQL and extracting CTEs...", spinner="dots"):
        parser = Parser()
        setup_sql, ctes = parser.extract_ctes(sql)
    
    if not ctes:
        console.print("[yellow]No CTEs found in the script. Nothing to autopsy.[/]")
        raise typer.Exit()
        
    with console.status("[bold green]Mapping dependencies...", spinner="dots"):
        grapher = DependencyGrapher()
        graph = grapher.build_graph(ctes)
        order = grapher.get_execution_order()
        
    with console.status("[bold green]Instrumenting SQL probes...", spinner="dots"):
        instrumentor = Instrumentor()
        materializations = instrumentor.get_materialization_statements(ctes, order)
        probes = instrumentor.get_probe_statements(order)
        
    with console.status("[bold green]Executing Autopsy against database...", spinner="dots"):
        executor = Executor(target=target)
        if setup_sql:
            executor.execute_setup(setup_sql)
            
        try:
            results = executor.run_autopsy(materializations, probes)
        except Exception as e:
            console.print(f"[bold red]Execution Failed:[/] {e}")
            raise typer.Exit(code=1)

    with console.status("[bold green]Diagnosing logical flaws...", spinner="dots"):
        diagnoser = Diagnoser(ctes, order, graph, results, executor)
        issues = diagnoser.diagnose()
        
    # Print Execution Summary
    table = Table(title="Execution Summary", show_header=True, header_style="bold magenta")
    table.add_column("Order")
    table.add_column("CTE Name")
    table.add_column("Row Count", justify="right")
    
    for i, cte_name in enumerate(order, 1):
        count = results.get(cte_name, 0)
        table.add_row(str(i), cte_name, str(count))
        
    console.print()
    console.print(table)
    console.print()
    
    # Print Diagnosis
    if not issues:
        console.print(Panel("[bold green]Success: No logical flaws detected. The query looks healthy![/]", border_style="green"))
    else:
        console.print(f"[bold red]Autopsy completed with {len(issues)} fatal flaw(s) found:[/]")
        for issue in issues:
            console.print()
            title = f"[bold red]{issue['type']}[/] in [bold cyan]{issue['cte']}[/]"
            console.print(title)
            console.print(f"[yellow]{issue['reason']}[/]")
            
            # Syntax Highlighting for the offending SQL
            syntax = Syntax(issue['sql'], "sql", theme="monokai", line_numbers=True)
            console.print(Panel(syntax, title="Offending SQL Snippet", border_style="red"))

if __name__ == "__main__":
    app()

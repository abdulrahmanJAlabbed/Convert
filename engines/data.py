"""Data transformation engine: CSV, JSON, Excel, YAML, XML conversions."""
import json
from pathlib import Path
from rich.console import Console


def csv_to_json(input_path: Path, console: Console):
    """Convert a CSV file to JSON."""
    import pandas as pd

    with console.status(f"[bold cyan]Converting {input_path.name} to JSON…[/bold cyan]"):
        df = pd.read_csv(input_path)
        out_path = input_path.with_suffix(".json")
        df.to_json(out_path, orient="records", indent=2, force_ascii=False)

    console.print(f"[bold green]✓ Converted {len(df)} rows → {out_path.name}[/bold green]")


def json_to_csv(input_path: Path, console: Console):
    """Convert a JSON file to CSV."""
    import pandas as pd

    with console.status(f"[bold cyan]Converting {input_path.name} to CSV…[/bold cyan]"):
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.json_normalize(data)
        else:
            raise ValueError("JSON must be an array of objects or a single object.")

        out_path = input_path.with_suffix(".csv")
        df.to_csv(out_path, index=False)

    console.print(f"[bold green]✓ Converted {len(df)} rows → {out_path.name}[/bold green]")


def excel_to_csv(input_path: Path, console: Console):
    """Convert an Excel file (.xlsx/.xls/.ods) to CSV."""
    import pandas as pd

    with console.status(f"[bold cyan]Converting {input_path.name} to CSV…[/bold cyan]"):
        # Read all sheets
        xls = pd.ExcelFile(input_path)
        sheets = xls.sheet_names

        if len(sheets) == 1:
            df = pd.read_excel(input_path, sheet_name=0)
            out_path = input_path.with_suffix(".csv")
            df.to_csv(out_path, index=False)
            console.print(f"[bold green]✓ Converted {len(df)} rows → {out_path.name}[/bold green]")
        else:
            console.print(f"[yellow]Found {len(sheets)} sheets: {', '.join(sheets)}[/yellow]")
            for sheet in sheets:
                df = pd.read_excel(input_path, sheet_name=sheet)
                safe_name = sheet.replace(" ", "_").replace("/", "_")
                out_path = input_path.parent / f"{input_path.stem}_{safe_name}.csv"
                df.to_csv(out_path, index=False)
                console.print(f"  [dim]+ {out_path.name} ({len(df)} rows)[/dim]")
            console.print(f"[bold green]✓ Exported {len(sheets)} sheets as CSV files.[/bold green]")


def csv_to_excel(input_path: Path, console: Console):
    """Convert a CSV file to Excel (.xlsx)."""
    import pandas as pd

    with console.status(f"[bold cyan]Converting {input_path.name} to Excel…[/bold cyan]"):
        df = pd.read_csv(input_path)
        out_path = input_path.with_suffix(".xlsx")
        df.to_excel(out_path, index=False, engine="openpyxl")

    console.print(f"[bold green]✓ Converted {len(df)} rows → {out_path.name}[/bold green]")


def yaml_to_json(input_path: Path, console: Console):
    """Convert a YAML file to JSON."""
    import yaml

    with console.status(f"[bold cyan]Converting {input_path.name} to JSON…[/bold cyan]"):
        with open(input_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        out_path = input_path.with_suffix(".json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    console.print(f"[bold green]✓ Converted → {out_path.name}[/bold green]")


def json_to_yaml(input_path: Path, console: Console):
    """Convert a JSON file to YAML."""
    import yaml

    with console.status(f"[bold cyan]Converting {input_path.name} to YAML…[/bold cyan]"):
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        out_path = input_path.with_suffix(".yaml")
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    console.print(f"[bold green]✓ Converted → {out_path.name}[/bold green]")


def json_prettify(input_path: Path, console: Console):
    """Pretty-print a JSON file with proper indentation."""
    with console.status(f"[bold cyan]Prettifying {input_path.name}…[/bold cyan]"):
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        out_path = input_path.parent / f"{input_path.stem}_pretty.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    console.print(f"[bold green]✓ Prettified → {out_path.name}[/bold green]")


def json_minify(input_path: Path, console: Console):
    """Minify a JSON file (remove all whitespace)."""
    with console.status(f"[bold cyan]Minifying {input_path.name}…[/bold cyan]"):
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        out_path = input_path.parent / f"{input_path.stem}_min.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"), ensure_ascii=False)

    original_kb = input_path.stat().st_size / 1024
    new_kb = out_path.stat().st_size / 1024
    console.print(f"[bold green]✓ Minified! {original_kb:.0f} KB → {new_kb:.0f} KB → {out_path.name}[/bold green]")

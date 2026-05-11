"""Entry point: ``python -m paperflow_tui`` and the ``paperflow-tui`` console script."""

from __future__ import annotations

import os

import click

from paperflow_tui.app import PaperflowTUI


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--base-url",
    "-u",
    default=lambda: os.environ.get("PAPERFLOW_BASE_URL", "http://127.0.0.1:8000"),
    show_default="http://127.0.0.1:8000",
    help="Paperflow backend base URL (FastAPI). Override with $PAPERFLOW_BASE_URL.",
)
def main(base_url: str) -> None:
    """Launch the Paperflow TUI.

    The backend must be running, e.g.::

        cd paperflow/backend
        . .venv/bin/activate
        uvicorn app.main:app --reload
    """
    PaperflowTUI(base_url=base_url).run()


if __name__ == "__main__":
    main()

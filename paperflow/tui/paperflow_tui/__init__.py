"""Paperflow TUI — terminal client for the Paperflow FastAPI backend.

The TUI keeps the Paperflow agent harness on the server side (`paperflow/backend`)
and acts as a thin Textual front-end talking to it over HTTP, mirroring the
DeepSeek-TUI separation of `app-server` and `tui`.
"""

from paperflow_tui.app import PaperflowTUI
from paperflow_tui.client import PaperflowClient

__all__ = ["PaperflowTUI", "PaperflowClient"]
__version__ = "0.1.0"

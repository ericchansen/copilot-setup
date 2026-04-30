"""BaseTab — abstract base for all configuration tabs.

Provides a split-pane layout (DataTable + DetailPane), inline filtering,
loading / error / empty states, and an action-dispatch mechanism that
subclasses override selectively.

Subclasses work with domain objects (frozen dataclasses), *not* raw tuples.
Each subclass overrides four small methods:

    load_items()       → list[T]           # data loading (runs in thread)
    key_for(item)      → str               # stable row identity
    row_for(item)      → tuple[Any, ...]   # visible columns
    detail_for(item)   → str               # Rich-markup detail text

And optionally:
    filter_text(item)  → str               # text searched by the filter bar
    handle_add/remove/edit/...()           # per-action handlers
"""

from __future__ import annotations

import itertools
import logging
from contextlib import suppress
from typing import Any, ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.widgets import DataTable, Label

from copilotsetup.widgets.detail_pane import DetailPane
from copilotsetup.widgets.filter_input import FilterInput

logger = logging.getLogger(__name__)


class BaseTab(Container):
    """Base class for every configuration tab.

    Subclasses **must** set:
        ``tab_name``  — human-readable label (e.g. ``"MCP Servers"``)
        ``columns``   — list of ``(header, width)`` for the DataTable

    Subclasses **may** set:
        ``available_actions`` — which single-key actions are active
    """

    # --- subclass overrides ---------------------------------------------------

    tab_name: str = ""
    columns: ClassVar[list[tuple[str, int]]] = []
    available_actions: ClassVar[list[str]] = []

    # --- messages -------------------------------------------------------------

    class DataLoaded(Message):
        """Posted after tab data has been (re)loaded."""

        def __init__(self, tab_name: str, row_count: int) -> None:
            self.tab_name = tab_name
            self.row_count = row_count
            super().__init__()

    class TabActivated(Message):
        """Posted when this tab becomes visible (updates footer bar)."""

        def __init__(self, available_actions: list[str]) -> None:
            self.available_actions = list(available_actions)
            super().__init__()

    # --- internal state -------------------------------------------------------

    def __init__(self, tab_label: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if tab_label:
            self.tab_name = tab_label
        self._items: list[Any] = []
        self._filtered_items: list[Any] = []
        self._current_filter: str = ""
        self._load_gen = itertools.count()
        self._active_gen: int = 0

    # --- compose --------------------------------------------------------------

    def compose(self) -> ComposeResult:
        slug = self.tab_name.lower().replace(" ", "-")
        yield FilterInput(id=f"filter-{slug}")
        with Horizontal(id="split-pane"):
            with Container(id="table-container"):
                yield DataTable(id="tab-table", cursor_type="row", zebra_stripes=True)
                yield Label("[dim]No items found[/]", id="empty-state", markup=True)
            yield DetailPane(id="detail-pane")

    # --- lifecycle ------------------------------------------------------------

    def on_mount(self) -> None:
        table = self.query_one("#tab-table", DataTable)
        for header, width in self.columns:
            table.add_column(header, width=width)
        table.loading = True
        self.query_one("#empty-state", Label).display = False
        self._start_load()

    def on_show(self) -> None:
        self.post_message(self.TabActivated(self.available_actions))

    # --- data loading ---------------------------------------------------------

    def _start_load(self) -> None:
        """Kick off a background load, recording its generation."""
        self._active_gen = next(self._load_gen)
        self._do_load(self._active_gen)

    @work(thread=True)
    async def _do_load(self, gen: int) -> None:
        """Worker thread: call ``load_items()``, then populate on main thread."""
        try:
            items = self.load_items()
        except Exception:
            logger.exception("Failed to load data for %s", self.tab_name)
            self.app.call_from_thread(self._show_error, gen)
            return
        self.app.call_from_thread(self._populate, items, gen)

    def _populate(self, items: list[Any], gen: int) -> None:
        """Main-thread callback: store items, rebuild table."""
        if gen != self._active_gen:
            return  # stale result from a superseded load
        self._items = items
        self._apply_filter()
        self.query_one("#tab-table", DataTable).loading = False
        self.post_message(self.DataLoaded(self.tab_name, len(items)))

    def _show_error(self, gen: int) -> None:
        """Main-thread callback: clear loading, show error state."""
        if gen != self._active_gen:
            return
        self._items = []
        self._filtered_items = []
        table = self.query_one("#tab-table", DataTable)
        table.loading = False
        table.clear()
        empty = self.query_one("#empty-state", Label)
        empty.update("[red]Error loading data — press [bold]r[/bold] to retry[/]")
        empty.display = True
        with suppress(Exception):
            self.query_one("#detail-pane", DetailPane).show_empty()

    # --- subclass data API (override these) -----------------------------------

    def load_items(self) -> list[Any]:
        """Return domain objects.  Runs in a worker thread — safe for I/O."""
        return []

    def key_for(self, item: Any) -> str:
        """Return a stable, unique key for *item* (used as DataTable row key)."""
        return str(id(item))

    def row_for(self, item: Any) -> tuple[Any, ...]:
        """Return the visible column values for *item*."""
        return ()

    def detail_for(self, item: Any) -> str:
        """Return Rich-markup text for the detail pane when *item* is highlighted."""
        parts: list[str] = []
        row = self.row_for(item)
        for (header, _width), value in zip(self.columns, row, strict=False):
            parts.append(f"[bold]{header}:[/] {value}")
        return "\n".join(parts)

    def filter_text(self, item: Any) -> str:
        """Return canonical text to match against the filter query.

        Defaults to joining all column values. Override for richer filtering.
        """
        return " ".join(str(v) for v in self.row_for(item))

    # --- refresh --------------------------------------------------------------

    def refresh_data(self) -> None:
        """Reload data from the provider (called on ``r``)."""
        self.query_one("#tab-table", DataTable).loading = True
        self.query_one("#empty-state", Label).update("[dim]No items found[/]")
        self._start_load()

    def focus_table(self) -> None:
        """Focus the DataTable so Up/Down navigate rows immediately."""
        with suppress(Exception):
            self.query_one("#tab-table", DataTable).focus()

    # --- filtering ------------------------------------------------------------

    def show_filter(self) -> None:
        self.query_one(FilterInput).show()

    @on(FilterInput.Updated)
    def _on_filter_updated(self, event: FilterInput.Updated) -> None:
        self._current_filter = event.query.lower()
        self._apply_filter()

    @on(FilterInput.Cleared)
    def _on_filter_cleared(self) -> None:
        self._current_filter = ""
        self._apply_filter()
        self.query_one("#tab-table", DataTable).focus()

    def _apply_filter(self) -> None:
        """Rebuild ``_filtered_items`` and repopulate the DataTable."""
        if self._current_filter:
            self._filtered_items = [
                item for item in self._items if self._current_filter in self.filter_text(item).lower()
            ]
        else:
            self._filtered_items = list(self._items)

        table = self.query_one("#tab-table", DataTable)
        table.clear()

        if self._filtered_items:
            for item in self._filtered_items:
                table.add_row(*self.row_for(item), key=self.key_for(item))
            self.query_one("#empty-state", Label).display = False
        else:
            self.query_one("#empty-state", Label).display = True

        with suppress(Exception):
            self.query_one("#detail-pane", DetailPane).show_empty()

    # --- row selection / detail sync ------------------------------------------

    @on(DataTable.RowHighlighted)
    def _on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        try:
            detail = self.query_one("#detail-pane", DetailPane)
        except Exception:
            return
        if event.cursor_row < 0 or event.cursor_row >= len(self._filtered_items):
            detail.show_empty()
            return
        item = self._filtered_items[event.cursor_row]
        detail.set_content(self.detail_for(item))

    def get_selected_item(self) -> Any | None:
        """Return the domain object for the currently highlighted row."""
        table = self.query_one("#tab-table", DataTable)
        idx = table.cursor_row
        if idx is not None and 0 <= idx < len(self._filtered_items):
            return self._filtered_items[idx]
        return None

    # --- action dispatch ------------------------------------------------------

    _ACTION_MAP: ClassVar[dict[str, str]] = {
        "a": "handle_add",
        "x": "handle_remove",
        "e": "handle_edit",
        "t": "handle_toggle",
        "u": "handle_upgrade",
        "m": "handle_marketplace",
        "h": "handle_health",
    }

    def dispatch_action(self, key: str) -> None:
        method_name = self._ACTION_MAP.get(key)
        if method_name and key in self.available_actions:
            getattr(self, method_name)()
        else:
            self.notify(
                f"[{key}] not available on this tab",
                severity="warning",
                title=self.tab_name,
            )

    # Default no-op handlers (subclasses override the ones they support)
    def handle_add(self) -> None: ...
    def handle_remove(self) -> None: ...
    def handle_edit(self) -> None: ...
    def handle_toggle(self) -> None: ...
    def handle_upgrade(self) -> None: ...
    def handle_marketplace(self) -> None: ...
    def handle_health(self) -> None: ...

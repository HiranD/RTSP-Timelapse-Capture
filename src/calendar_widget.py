"""
Calendar Widget - Custom 2-month calendar for astronomical scheduling
Displays current month and next month side by side with date selection.

Features:
- Click dates to toggle selection on/off
- Visual indicators: captured (green), scheduled (blue), past (gray), today (bordered)
- Navigation arrows to view future months
- Select All / Clear All buttons
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, date, timedelta
from typing import Set, Callable, Optional
from pathlib import Path
import calendar


class TwoMonthCalendar(ttk.Frame):
    """
    Custom calendar widget showing 2 months side by side.

    Allows clicking dates to toggle capture scheduling on/off.
    Checks snapshots folder to show which dates have captures.
    """

    # Visual styling
    COLORS = {
        "captured": "#90EE90",      # Light green - past date with images
        "scheduled": "#87CEEB",     # Light blue - future date selected
        "past": "#E0E0E0",          # Gray - past date without captures
        "today_bg": "#FFFFFF",      # White background for today
        "today_border": "#FF6B6B",  # Red border for today
        "future": "#FFFFFF",        # White - future date not selected
        "header": "#4A90D9",        # Blue header
        "weekend": "#F5F5F5",       # Slightly gray for weekends
    }

    DAY_NAMES = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]

    def __init__(
        self,
        parent,
        snapshots_dir: str = "snapshots",
        on_selection_change: Optional[Callable[[Set[str]], None]] = None,
        **kwargs
    ):
        """
        Initialize the two-month calendar widget.

        Args:
            parent: Parent tkinter widget
            snapshots_dir: Directory to check for captured dates (YYYYMMDD folders)
            on_selection_change: Callback when selection changes, receives set of date strings
        """
        super().__init__(parent, **kwargs)

        self.snapshots_dir = Path(snapshots_dir)
        self.on_selection_change = on_selection_change

        # Selected dates (future dates user wants to capture)
        self.selected_dates: Set[str] = set()  # Format: "YYYY-MM-DD"

        # Current view: first day of the left month
        today = date.today()
        self.view_date = date(today.year, today.month, 1)

        # Store day label references for updating
        self._day_labels = {}  # {(month_offset, row, col): label}

        self._create_widgets()
        self._update_display()

    def _create_widgets(self):
        """Create all calendar widgets"""
        # Main container - center content horizontally
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)  # Content column
        self.columnconfigure(2, weight=1)

        # Inner frame to hold all content (will be centered)
        inner_frame = ttk.Frame(self)
        inner_frame.grid(row=0, column=1, sticky="n")

        # Main horizontal container: calendar section + buttons
        main_frame = ttk.Frame(inner_frame)
        main_frame.grid(row=0, column=0, sticky="n")

        # === Left side: Calendar with navigation ===
        cal_container = ttk.Frame(main_frame)
        cal_container.grid(row=0, column=0, sticky="n")

        # Navigation header with arrows (inside calendar container)
        nav_frame = ttk.Frame(cal_container)
        nav_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        nav_frame.columnconfigure(1, weight=1)

        self.prev_btn = ttk.Button(nav_frame, text="<", width=3, command=self._prev_month)
        self.prev_btn.grid(row=0, column=0, padx=(0, 5))

        self.month_label = ttk.Label(nav_frame, text="", font=("Segoe UI", 10, "bold"))
        self.month_label.grid(row=0, column=1)

        self.next_btn = ttk.Button(nav_frame, text=">", width=3, command=self._next_month)
        self.next_btn.grid(row=0, column=2, padx=(5, 0))

        # Calendar months (two months side by side)
        cal_frame = ttk.Frame(cal_container)
        cal_frame.grid(row=1, column=0, sticky="n")

        # Left month (current view)
        self.left_month_frame = ttk.Frame(cal_frame)
        self.left_month_frame.grid(row=0, column=0, sticky="n", padx=(0, 10))
        self._create_month_grid(self.left_month_frame, 0)

        # Separator
        ttk.Separator(cal_frame, orient="vertical").grid(row=0, column=1, sticky="ns", padx=5)

        # Right month (next month)
        self.right_month_frame = ttk.Frame(cal_frame)
        self.right_month_frame.grid(row=0, column=2, sticky="n", padx=(10, 0))
        self._create_month_grid(self.right_month_frame, 1)

        # === Right side: Action buttons ===
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=0, column=1, sticky="ns", padx=(20, 0))

        # Spacer to push buttons down (align with calendar middle)
        ttk.Frame(btn_frame).pack(pady=(40, 0))
        ttk.Button(btn_frame, text="Select All", width=10, command=self._select_all).pack(pady=(0, 5))
        ttk.Button(btn_frame, text="Clear All", width=10, command=self._clear_all).pack()

        # Legend (below buttons as vertical list)
        legend_frame = ttk.Frame(btn_frame)
        legend_frame.pack(pady=(15, 0))

        self._create_legend_item(legend_frame, self.COLORS["captured"], "Captured")
        self._create_legend_item(legend_frame, self.COLORS["scheduled"], "Scheduled")
        self._create_legend_item(legend_frame, self.COLORS["past"], "Past")

    def _create_month_grid(self, parent: ttk.Frame, month_offset: int):
        """
        Create a single month grid.

        Args:
            parent: Parent frame
            month_offset: 0 for left month, 1 for right month
        """
        # Month/Year header
        header = ttk.Label(parent, text="", font=("Segoe UI", 9, "bold"))
        header.grid(row=0, column=0, columnspan=7, pady=(0, 5))
        self._day_labels[(month_offset, -1, 0)] = header  # Store header reference

        # Day name headers
        for col, day_name in enumerate(self.DAY_NAMES):
            lbl = ttk.Label(parent, text=day_name, font=("Segoe UI", 8), width=3, anchor="center")
            lbl.grid(row=1, column=col, padx=1, pady=1)

        # Day cells (6 rows x 7 columns)
        for row in range(6):
            for col in range(7):
                # Create a frame for each day cell (to handle border)
                cell_frame = tk.Frame(parent, width=30, height=26)
                cell_frame.grid(row=row + 2, column=col, padx=1, pady=1)
                cell_frame.grid_propagate(False)

                # Label inside the frame
                lbl = tk.Label(
                    cell_frame,
                    text="",
                    font=("Segoe UI", 9),
                    width=3,
                    height=1,
                    cursor="hand2"
                )
                lbl.place(relx=0.5, rely=0.5, anchor="center")

                # Bind click event
                lbl.bind("<Button-1>", lambda e, mo=month_offset, r=row, c=col: self._on_day_click(mo, r, c))
                cell_frame.bind("<Button-1>", lambda e, mo=month_offset, r=row, c=col: self._on_day_click(mo, r, c))

                # Store references
                self._day_labels[(month_offset, row, col)] = (cell_frame, lbl)

    def _create_legend_item(self, parent: ttk.Frame, color: str, text: str):
        """Create a legend item with color box and label"""
        item_frame = ttk.Frame(parent)
        item_frame.pack(anchor="w", pady=2)

        color_box = tk.Frame(item_frame, width=12, height=12, bg=color, relief="solid", borderwidth=1)
        color_box.pack(side="left", padx=(0, 4))

        ttk.Label(item_frame, text=text, font=("Segoe UI", 8)).pack(side="left")

    def _update_display(self):
        """Update the calendar display"""
        # Update month header label
        left_month = self.view_date
        right_month = self._add_months(self.view_date, 1)

        self.month_label.config(
            text=f"{left_month.strftime('%B %Y')}  |  {right_month.strftime('%B %Y')}"
        )

        # Update left month
        self._update_month_grid(0, left_month)

        # Update right month
        self._update_month_grid(1, right_month)

    def _update_month_grid(self, month_offset: int, month_date: date):
        """Update a single month grid"""
        # Update header
        header = self._day_labels[(month_offset, -1, 0)]
        header.config(text=month_date.strftime("%B %Y"))

        # Get calendar data
        cal = calendar.Calendar(firstweekday=6)  # Sunday first
        month_days = list(cal.itermonthdays(month_date.year, month_date.month))

        # Pad to 42 days (6 weeks)
        while len(month_days) < 42:
            month_days.append(0)

        today = date.today()

        # Update each cell
        for row in range(6):
            for col in range(7):
                idx = row * 7 + col
                day = month_days[idx]

                cell_frame, lbl = self._day_labels[(month_offset, row, col)]

                if day == 0:
                    # Empty cell
                    lbl.config(text="", bg=self.COLORS["future"])
                    cell_frame.config(bg=self.COLORS["future"], highlightthickness=0)
                else:
                    current_date = date(month_date.year, month_date.month, day)
                    date_str = current_date.strftime("%Y-%m-%d")

                    lbl.config(text=str(day))

                    # Determine cell status and color
                    status = self._get_date_status(current_date, date_str)
                    bg_color = self._get_status_color(status)

                    lbl.config(bg=bg_color)
                    cell_frame.config(bg=bg_color)

                    # Special border for today
                    if current_date == today:
                        cell_frame.config(
                            highlightbackground=self.COLORS["today_border"],
                            highlightthickness=2
                        )
                    else:
                        cell_frame.config(highlightthickness=0)

    def _get_date_status(self, current_date: date, date_str: str) -> str:
        """
        Determine the status of a date.

        Returns: "captured", "scheduled", "past", "today", or "future"
        """
        today = date.today()

        if current_date < today:
            # Past date - check if captured
            if self._has_captures(current_date):
                return "captured"
            return "past"
        elif current_date == today:
            # Today - check if scheduled
            if date_str in self.selected_dates:
                return "scheduled"
            return "today"
        else:
            # Future date
            if date_str in self.selected_dates:
                return "scheduled"
            return "future"

    def _get_status_color(self, status: str) -> str:
        """Get background color for a date status"""
        color_map = {
            "captured": self.COLORS["captured"],
            "scheduled": self.COLORS["scheduled"],
            "past": self.COLORS["past"],
            "today": self.COLORS["today_bg"],
            "future": self.COLORS["future"],
        }
        return color_map.get(status, self.COLORS["future"])

    def _has_captures(self, check_date: date) -> bool:
        """Check if a date has captured images in the snapshots folder"""
        date_folder = self.snapshots_dir / check_date.strftime("%Y%m%d")

        if not date_folder.exists():
            return False

        # Check for any jpg files
        return any(date_folder.glob("*.jpg")) or any(date_folder.glob("*.jpeg"))

    def _on_day_click(self, month_offset: int, row: int, col: int):
        """Handle click on a day cell"""
        # Calculate which date was clicked
        month_date = self._add_months(self.view_date, month_offset)

        cal = calendar.Calendar(firstweekday=6)
        month_days = list(cal.itermonthdays(month_date.year, month_date.month))

        idx = row * 7 + col
        if idx >= len(month_days):
            return

        day = month_days[idx]
        if day == 0:
            return

        clicked_date = date(month_date.year, month_date.month, day)
        today = date.today()

        # Only allow selecting today or future dates
        if clicked_date < today:
            return

        date_str = clicked_date.strftime("%Y-%m-%d")

        # Toggle selection
        if date_str in self.selected_dates:
            self.selected_dates.remove(date_str)
        else:
            self.selected_dates.add(date_str)

        # Update display
        self._update_display()

        # Notify callback
        if self.on_selection_change:
            self.on_selection_change(self.selected_dates.copy())

    def _prev_month(self):
        """Navigate to previous month"""
        self.view_date = self._add_months(self.view_date, -1)
        self._update_display()

    def _next_month(self):
        """Navigate to next month"""
        self.view_date = self._add_months(self.view_date, 1)
        self._update_display()

    def _add_months(self, d: date, months: int) -> date:
        """Add months to a date"""
        month = d.month + months
        year = d.year

        while month > 12:
            month -= 12
            year += 1
        while month < 1:
            month += 12
            year -= 1

        return date(year, month, 1)

    def _select_all(self):
        """Select all future dates in the visible months"""
        today = date.today()

        for month_offset in range(2):
            month_date = self._add_months(self.view_date, month_offset)

            # Get all days in this month
            _, num_days = calendar.monthrange(month_date.year, month_date.month)

            for day in range(1, num_days + 1):
                d = date(month_date.year, month_date.month, day)
                if d >= today:
                    self.selected_dates.add(d.strftime("%Y-%m-%d"))

        self._update_display()

        if self.on_selection_change:
            self.on_selection_change(self.selected_dates.copy())

    def _clear_all(self):
        """Clear all selected dates"""
        self.selected_dates.clear()
        self._update_display()

        if self.on_selection_change:
            self.on_selection_change(self.selected_dates.copy())

    # Public API

    def get_selected_dates(self) -> Set[str]:
        """Get set of selected date strings (YYYY-MM-DD format)"""
        return self.selected_dates.copy()

    def set_selected_dates(self, dates: Set[str]):
        """Set selected dates from a set of date strings"""
        self.selected_dates = set(dates)
        self._update_display()

    def set_snapshots_dir(self, path: str):
        """Update the snapshots directory path"""
        self.snapshots_dir = Path(path)
        self._update_display()


def test_calendar_widget():
    """Test the calendar widget"""
    root = tk.Tk()
    root.title("Calendar Widget Test")
    root.geometry("580x420")

    def on_selection_change(dates):
        print(f"Selected dates: {sorted(dates)}")

    calendar_widget = TwoMonthCalendar(
        root,
        snapshots_dir="snapshots",
        on_selection_change=on_selection_change
    )
    calendar_widget.pack(fill="both", expand=True, padx=20, pady=20)

    root.mainloop()


if __name__ == "__main__":
    test_calendar_widget()

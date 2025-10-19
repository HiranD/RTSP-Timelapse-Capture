"""
ToolTip - Hover tooltip widget for Tkinter
Phase 3.6: GUI Tooltip Enhancement

Provides a reusable tooltip class that displays helpful text when hovering
over widgets. Features configurable delay, smart positioning, and clean styling.
"""

import tkinter as tk
from typing import Optional


class ToolTip:
    """
    Create a tooltip for a given widget.

    Shows a small popup window with helpful text when the user hovers
    over a widget. The tooltip appears after a configurable delay and
    automatically positions itself near the widget.

    Example:
        button = ttk.Button(root, text="Save")
        ToolTip(button, "Save current settings to file (Ctrl+S)")
    """

    def __init__(
        self,
        widget: tk.Widget,
        text: str,
        delay: int = 500,
        wraplength: int = 300,
        bg: str = "#FFFFE0",
        fg: str = "#000000",
        border_width: int = 1,
        border_color: str = "#888888"
    ):
        """
        Initialize tooltip for a widget.

        Args:
            widget: Tkinter widget to attach tooltip to
            text: Tooltip message text
            delay: Milliseconds before showing tooltip (default: 500)
            wraplength: Maximum width in pixels before text wraps (default: 300)
            bg: Background color (default: light yellow #FFFFE0)
            fg: Foreground/text color (default: black)
            border_width: Border thickness in pixels (default: 1)
            border_color: Border color (default: gray #888888)
        """
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wraplength = wraplength
        self.bg = bg
        self.fg = fg
        self.border_width = border_width
        self.border_color = border_color

        # Tooltip window (created when needed)
        self.tooltip_window: Optional[tk.Toplevel] = None

        # Scheduled callback for showing tooltip
        self.schedule_id: Optional[str] = None

        # Bind mouse events
        self.widget.bind("<Enter>", self.on_enter, add="+")
        self.widget.bind("<Leave>", self.on_leave, add="+")
        self.widget.bind("<Button>", self.on_leave, add="+")  # Hide on click

    def on_enter(self, event=None):
        """
        Handle mouse entering widget.
        Schedule tooltip to appear after delay.
        """
        # Cancel any existing scheduled tooltip
        if self.schedule_id:
            self.widget.after_cancel(self.schedule_id)

        # Schedule tooltip to appear after delay
        self.schedule_id = self.widget.after(self.delay, self.show_tooltip)

    def on_leave(self, event=None):
        """
        Handle mouse leaving widget.
        Cancel scheduled tooltip and hide if visible.
        """
        # Cancel scheduled tooltip
        if self.schedule_id:
            self.widget.after_cancel(self.schedule_id)
            self.schedule_id = None

        # Hide tooltip if visible
        self.hide_tooltip()

    def show_tooltip(self):
        """
        Display the tooltip window near the widget.
        """
        # Don't show if widget is disabled
        if str(self.widget.cget("state")) == "disabled":
            return

        # Don't create duplicate tooltips
        if self.tooltip_window:
            return

        # Get widget position
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty()
        widget_height = self.widget.winfo_height()

        # Create tooltip window
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)  # Remove window decorations

        # Create label with tooltip text
        label = tk.Label(
            self.tooltip_window,
            text=self.text,
            justify=tk.LEFT,
            background=self.bg,
            foreground=self.fg,
            relief=tk.SOLID,
            borderwidth=self.border_width,
            wraplength=self.wraplength,
            font=("Segoe UI", 9),
            padx=8,
            pady=6
        )
        label.pack()

        # Update to get actual size
        self.tooltip_window.update_idletasks()
        tooltip_width = self.tooltip_window.winfo_width()
        tooltip_height = self.tooltip_window.winfo_height()

        # Get screen dimensions
        screen_width = self.tooltip_window.winfo_screenwidth()
        screen_height = self.tooltip_window.winfo_screenheight()

        # Calculate position (below and slightly right of widget)
        tooltip_x = x + 10
        tooltip_y = y + widget_height + 5

        # Adjust if tooltip would go off screen (right edge)
        if tooltip_x + tooltip_width > screen_width - 10:
            tooltip_x = screen_width - tooltip_width - 10

        # Adjust if tooltip would go off screen (bottom edge)
        if tooltip_y + tooltip_height > screen_height - 10:
            # Show above widget instead
            tooltip_y = y - tooltip_height - 5

        # Ensure tooltip stays on screen (left edge)
        if tooltip_x < 10:
            tooltip_x = 10

        # Ensure tooltip stays on screen (top edge)
        if tooltip_y < 10:
            tooltip_y = 10

        # Position and show tooltip
        self.tooltip_window.wm_geometry(f"+{tooltip_x}+{tooltip_y}")

        # Configure border color
        if self.border_width > 0:
            label.config(highlightbackground=self.border_color, highlightthickness=self.border_width)

    def hide_tooltip(self):
        """
        Hide and destroy the tooltip window.
        """
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def update_text(self, new_text: str):
        """
        Update tooltip text (useful for dynamic tooltips).

        Args:
            new_text: New tooltip message
        """
        self.text = new_text

        # If tooltip is currently shown, update it
        if self.tooltip_window:
            self.hide_tooltip()
            self.show_tooltip()


def demo():
    """Demo/test the ToolTip class"""
    import tkinter.ttk as ttk

    root = tk.Tk()
    root.title("ToolTip Demo")
    root.geometry("500x400")

    # Create demo widgets with tooltips
    frame = ttk.Frame(root, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    # Button with short tooltip
    btn1 = ttk.Button(frame, text="Save")
    btn1.pack(pady=10)
    ToolTip(btn1, "Save current settings to file (Ctrl+S)")

    # Button with long tooltip (will wrap)
    btn2 = ttk.Button(frame, text="Export Video")
    btn2.pack(pady=10)
    ToolTip(btn2,
            "Export captured images to video using FFmpeg. "
            "You can customize frame rate, quality, resolution, and speed. "
            "The original images will be preserved if that option is enabled.")

    # Entry with tooltip
    entry = ttk.Entry(frame, width=30)
    entry.pack(pady=10)
    entry.insert(0, "192.168.0.101")
    ToolTip(entry, "IP address of your RTSP camera on the network")

    # Checkbox with tooltip
    var = tk.BooleanVar(value=True)
    check = ttk.Checkbutton(frame, text="Force TCP", variable=var)
    check.pack(pady=10)
    ToolTip(check,
            "Use TCP instead of UDP for more reliable connection. "
            "Recommended for IP cameras to prevent frame drops.")

    # Spinbox with tooltip
    spin = ttk.Spinbox(frame, from_=1, to=120, width=10)
    spin.pack(pady=10)
    ToolTip(spin,
            "Video frame rate (fps). "
            "24 = cinematic, 30 = smooth, 60 = ultra-smooth")

    # Disabled widget (tooltip should still work)
    btn_disabled = ttk.Button(frame, text="Disabled Button", state="disabled")
    btn_disabled.pack(pady=10)
    ToolTip(btn_disabled, "This button is currently disabled")

    # Label
    label = ttk.Label(frame, text="Hover over widgets to see tooltips!")
    label.pack(pady=20)

    root.mainloop()


if __name__ == "__main__":
    demo()

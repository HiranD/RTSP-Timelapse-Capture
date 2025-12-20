"""
Video Export Panel - GUI component for video export
Phase 3.5: Video Export Feature

Provides user interface for video export with presets, settings, and progress tracking.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from typing import Optional
import os
import sys


def get_app_base_dir() -> Path:
    """Get the application's base directory (where exe or main script is located)."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - use exe's directory
        return Path(sys.executable).parent
    else:
        # Running from source - use src's parent directory
        return Path(__file__).parent.parent


def resolve_path(path_str: str) -> Path:
    """Resolve a path - if relative, resolve from app base directory."""
    path = Path(path_str)
    if path.is_absolute():
        return path
    else:
        return (get_app_base_dir() / path).resolve()

from video_export_controller import VideoExportController, ImageCollection, ExportJob, ExportResult
from preset_manager import PresetManager, VideoExportSettings
from ffmpeg_wrapper import FFmpegWrapper, ProgressInfo
from tooltip import ToolTip
from video_export_tooltips import VIDEO_EXPORT_TOOLTIPS


class VideoExportPanel(ttk.Frame):
    """Video export tab UI component"""

    def __init__(self, parent, default_snapshots_dir: str = "snapshots", config_manager=None):
        """
        Initialize video export panel

        Args:
            parent: Parent widget
            default_snapshots_dir: Default directory containing snapshots
            config_manager: ConfigManager instance for saving/loading preferences
        """
        super().__init__(parent, padding="10")

        self.default_snapshots_dir = resolve_path(default_snapshots_dir)
        self.config_manager = config_manager

        # Initialize components
        self.ffmpeg_wrapper = FFmpegWrapper()
        self.controller = VideoExportController(self.ffmpeg_wrapper)
        self.preset_manager = PresetManager()

        # Current state
        self.current_collection: Optional[ImageCollection] = None
        self.current_job: Optional[ExportJob] = None
        self.is_exporting = False
        self._get_snapshots_dir_callback = None  # Callback to get current snapshots dir from Capture tab
        self._session_browse_dir = None  # Session-only: user's manual folder selection (not saved)

        # Create UI
        self.create_widgets()
        self.check_ffmpeg_status()

        # Load last used settings if available
        self.load_last_settings()

    def create_widgets(self):
        """Create all UI widgets"""

        # Configure grid weights
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=0)  # Progress section doesn't expand
        self.rowconfigure(4, weight=1)  # Log section expands

        # Input Selection Section
        self.create_input_section()

        # Video Settings Section
        self.create_settings_section()

        # Output Options Section
        self.create_output_section()

        # Presets Section
        self.create_presets_section()

        # Progress Section
        self.create_progress_section()

        # Log Section
        self.create_log_section()

        # Action Buttons
        self.create_action_buttons()

    def create_input_section(self):
        """Create input selection section"""
        input_frame = ttk.LabelFrame(self, text="Input Selection", padding="10")
        input_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)

        row = 0

        # Source folder
        ttk.Label(input_frame, text="Source Folder:").grid(row=row, column=0, sticky=tk.W, pady=5)

        folder_frame = ttk.Frame(input_frame)
        folder_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        folder_frame.columnconfigure(0, weight=1)

        self.source_folder_entry = ttk.Entry(folder_frame)
        self.source_folder_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        ToolTip(self.source_folder_entry, VIDEO_EXPORT_TOOLTIPS["source_folder"])

        browse_btn = ttk.Button(folder_frame, text="Browse", command=self.browse_source_folder, width=10)
        browse_btn.grid(row=0, column=1, padx=(5, 0))
        ToolTip(browse_btn, VIDEO_EXPORT_TOOLTIPS["browse_source"])

        quick_select_btn = ttk.Button(folder_frame, text="Quick Select", command=self.quick_select_folder, width=12)
        quick_select_btn.grid(row=0, column=2, padx=(5, 0))
        ToolTip(quick_select_btn, VIDEO_EXPORT_TOOLTIPS["quick_select"])

        row += 1

        # Image info
        self.image_info_label = ttk.Label(input_frame, text="No folder selected", foreground="gray")
        self.image_info_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 5), padx=(0, 0))
        ToolTip(self.image_info_label, VIDEO_EXPORT_TOOLTIPS["image_info"])

    def create_settings_section(self):
        """Create video settings section"""
        settings_frame = ttk.LabelFrame(self, text="Video Settings", padding="10")
        settings_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        settings_frame.columnconfigure(1, weight=1)
        settings_frame.columnconfigure(3, weight=1)

        row = 0

        # Frame rate
        ttk.Label(settings_frame, text="Frame Rate:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.framerate_var = tk.IntVar(value=24)
        framerate_frame = ttk.Frame(settings_frame)
        framerate_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 10))
        self.framerate_spinbox = ttk.Spinbox(framerate_frame, from_=1, to=120, textvariable=self.framerate_var, width=10)
        self.framerate_spinbox.pack(side=tk.LEFT)
        ToolTip(self.framerate_spinbox, VIDEO_EXPORT_TOOLTIPS["framerate"])
        ttk.Label(framerate_frame, text="fps").pack(side=tk.LEFT, padx=(5, 0))

        # Quality (CRF)
        ttk.Label(settings_frame, text="Quality (CRF):").grid(row=row, column=2, sticky=tk.W, pady=5, padx=(10, 0))
        quality_frame = ttk.Frame(settings_frame)
        quality_frame.grid(row=row, column=3, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        self.quality_var = tk.IntVar(value=20)
        self.quality_spinbox = ttk.Spinbox(quality_frame, from_=0, to=51, textvariable=self.quality_var, width=10)
        self.quality_spinbox.pack(side=tk.LEFT)
        ToolTip(self.quality_spinbox, VIDEO_EXPORT_TOOLTIPS["quality_crf"])
        ttk.Label(quality_frame, text="(lower=better)").pack(side=tk.LEFT, padx=(5, 0))

        row += 1

        # Speed multiplier
        ttk.Label(settings_frame, text="Speed Multiplier:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.speed_var = tk.IntVar(value=1)
        speed_frame = ttk.Frame(settings_frame)
        speed_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 10))
        self.speed_combo = ttk.Combobox(speed_frame, textvariable=self.speed_var, width=8, state='readonly',
                                        values=[1, 2, 4, 8, 16, 32])
        self.speed_combo.pack(side=tk.LEFT)
        ToolTip(self.speed_combo, VIDEO_EXPORT_TOOLTIPS["speed_multiplier"])
        ttk.Label(speed_frame, text="x").pack(side=tk.LEFT, padx=(5, 0))

        # Resolution
        ttk.Label(settings_frame, text="Resolution:").grid(row=row, column=2, sticky=tk.W, pady=5, padx=(10, 0))
        self.resolution_var = tk.StringVar(value='original')
        resolution_frame = ttk.Frame(settings_frame)
        resolution_frame.grid(row=row, column=3, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        self.resolution_combo = ttk.Combobox(resolution_frame, textvariable=self.resolution_var, width=15, state='readonly',
                                             values=self.preset_manager.get_resolution_options())
        self.resolution_combo.pack(side=tk.LEFT)
        ToolTip(self.resolution_combo, VIDEO_EXPORT_TOOLTIPS["resolution"])

        row += 1

        # Format
        ttk.Label(settings_frame, text="Format:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.format_var = tk.StringVar(value='mp4')
        format_frame = ttk.Frame(settings_frame)
        format_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 10))
        self.format_combo = ttk.Combobox(format_frame, textvariable=self.format_var, width=8, state='readonly',
                                         values=self.preset_manager.get_format_options())
        self.format_combo.pack(side=tk.LEFT)
        ToolTip(self.format_combo, VIDEO_EXPORT_TOOLTIPS["format"])

        # Estimated info
        ttk.Label(settings_frame, text="Estimated:").grid(row=row, column=2, sticky=tk.W, pady=5, padx=(10, 0))
        self.estimate_label = ttk.Label(settings_frame, text="Select folder first", foreground="gray")
        self.estimate_label.grid(row=row, column=3, sticky=tk.W, pady=5, padx=(5, 0))
        ToolTip(self.estimate_label, VIDEO_EXPORT_TOOLTIPS["estimate"])

        # Bind change events to update estimates
        self.framerate_var.trace_add('write', lambda *args: self.update_estimates())
        self.quality_var.trace_add('write', lambda *args: self.update_estimates())
        self.speed_var.trace_add('write', lambda *args: self.update_estimates())
        self.resolution_var.trace_add('write', lambda *args: self.update_estimates())

    def create_output_section(self):
        """Create output options section"""
        output_frame = ttk.LabelFrame(self, text="Output Options", padding="10")
        output_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        output_frame.columnconfigure(1, weight=1)

        row = 0

        # Output file
        ttk.Label(output_frame, text="Output File:").grid(row=row, column=0, sticky=tk.W, pady=5)

        file_frame = ttk.Frame(output_frame)
        file_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        file_frame.columnconfigure(0, weight=1)

        self.output_file_entry = ttk.Entry(file_frame)
        self.output_file_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))

        # Set initial default path (current directory or last used directory)
        if self.config_manager and self.config_manager.ui.last_video_export_dir:
            default_path = Path(self.config_manager.ui.last_video_export_dir) / "timelapse.mp4"
        else:
            default_path = Path(os.getcwd()) / "timelapse.mp4"

        self.output_file_entry.insert(0, str(default_path))
        ToolTip(self.output_file_entry, VIDEO_EXPORT_TOOLTIPS["output_file"])

        browse_output_btn = ttk.Button(file_frame, text="Browse", command=self.browse_output_file, width=10)
        browse_output_btn.grid(row=0, column=1, padx=(5, 0))
        ToolTip(browse_output_btn, VIDEO_EXPORT_TOOLTIPS["browse_output"])

        row += 1

        # Options checkboxes
        options_frame = ttk.Frame(output_frame)
        options_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5)

        self.preserve_originals_var = tk.BooleanVar(value=True)
        preserve_check = ttk.Checkbutton(options_frame, text="Preserve original filenames (create temp copies)",
                        variable=self.preserve_originals_var)
        preserve_check.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(preserve_check, VIDEO_EXPORT_TOOLTIPS["preserve_originals"])

        self.add_timestamp_var = tk.BooleanVar(value=False)
        timestamp_check = ttk.Checkbutton(options_frame, text="Add frame counter overlay",
                        variable=self.add_timestamp_var)
        timestamp_check.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(timestamp_check, VIDEO_EXPORT_TOOLTIPS["frame_counter"])

        self.open_when_done_var = tk.BooleanVar(value=False)
        open_check = ttk.Checkbutton(options_frame, text="Open video when complete",
                        variable=self.open_when_done_var)
        open_check.pack(side=tk.LEFT)
        ToolTip(open_check, VIDEO_EXPORT_TOOLTIPS["open_when_done"])

    def create_presets_section(self):
        """Create presets section"""
        presets_frame = ttk.LabelFrame(self, text="Presets", padding="10")
        presets_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Preset selection
        preset_select_frame = ttk.Frame(presets_frame)
        preset_select_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(preset_select_frame, text="Quick Select:").pack(side=tk.LEFT, padx=(0, 5))

        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(preset_select_frame, textvariable=self.preset_var,
                                         width=25, state='readonly')
        self.preset_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.preset_combo['values'] = self.preset_manager.list_presets()
        self.preset_combo.bind('<<ComboboxSelected>>', self.load_preset)
        ToolTip(self.preset_combo, VIDEO_EXPORT_TOOLTIPS["preset_select"])

        # Preset buttons
        save_preset_btn = ttk.Button(preset_select_frame, text="Save As Preset", command=self.save_as_preset)
        save_preset_btn.pack(side=tk.LEFT, padx=2)
        ToolTip(save_preset_btn, VIDEO_EXPORT_TOOLTIPS["save_preset"])

        manage_presets_btn = ttk.Button(preset_select_frame, text="Manage Presets", command=self.manage_presets)
        manage_presets_btn.pack(side=tk.LEFT, padx=2)
        ToolTip(manage_presets_btn, VIDEO_EXPORT_TOOLTIPS["manage_presets"])

    def create_progress_section(self):
        """Create progress section"""
        progress_frame = ttk.LabelFrame(self, text="Progress", padding="10")
        progress_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)

        # Status label
        self.status_label = ttk.Label(progress_frame, text="Ready", font=("Arial", 10, "bold"))
        self.status_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        ToolTip(self.status_label, VIDEO_EXPORT_TOOLTIPS["status"])

        # Progress bar
        self.progress_bar = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 5))

        # Progress details
        self.progress_details_label = ttk.Label(progress_frame, text="", foreground="gray")
        self.progress_details_label.grid(row=2, column=0, sticky=tk.W)
        ToolTip(self.progress_details_label, VIDEO_EXPORT_TOOLTIPS["progress_details"])

    def create_log_section(self):
        """Create log section"""
        log_frame = ttk.LabelFrame(self, text="Export Log", padding="10")
        log_frame.grid(row=5, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        # Scrolled text for log
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=8, state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Clear button
        ttk.Button(log_frame, text="Clear Log", command=self.clear_log).grid(row=1, column=0, sticky=tk.E, pady=(5, 0))

    def create_action_buttons(self):
        """Create action buttons at bottom"""
        button_frame = ttk.Frame(self)
        button_frame.grid(row=6, column=0, sticky=(tk.W, tk.E))

        self.create_video_btn = ttk.Button(button_frame, text="Create Video", command=self.start_export)
        self.create_video_btn.pack(side=tk.RIGHT, padx=5)
        ToolTip(self.create_video_btn, VIDEO_EXPORT_TOOLTIPS["create_video"])

        self.cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.cancel_export, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.RIGHT, padx=5)
        ToolTip(self.cancel_btn, VIDEO_EXPORT_TOOLTIPS["cancel"])

        self.test_ffmpeg_btn = ttk.Button(button_frame, text="Test FFmpeg", command=self.test_ffmpeg)
        self.test_ffmpeg_btn.pack(side=tk.LEFT, padx=5)
        ToolTip(self.test_ffmpeg_btn, VIDEO_EXPORT_TOOLTIPS["test_ffmpeg"])

    # Event handlers

    def browse_source_folder(self):
        """Browse for source folder"""
        # Always start at output folder from Capture tab
        initial_dir = str(self._get_current_snapshots_dir())
        folder = filedialog.askdirectory(title="Select Image Folder", initialdir=initial_dir)

        if folder:
            self.source_folder_entry.delete(0, tk.END)
            self.source_folder_entry.insert(0, folder)
            # Remember this selection for session (for Quick Select to use)
            self._session_browse_dir = folder
            self.scan_source_folder()

    def set_snapshots_dir_callback(self, callback):
        """Set callback to get current snapshots directory from Capture tab."""
        self._get_snapshots_dir_callback = callback

    def _get_current_snapshots_dir(self) -> Path:
        """Get current snapshots directory from Capture tab or config."""
        if self._get_snapshots_dir_callback:
            return resolve_path(self._get_snapshots_dir_callback())
        elif self.config_manager:
            return resolve_path(self.config_manager.capture.output_folder)
        else:
            return self.default_snapshots_dir

    def quick_select_folder(self):
        """Quick select from available date folders"""
        # Use session browse dir if user manually selected a location, otherwise use output folder
        if self._session_browse_dir and Path(self._session_browse_dir).exists():
            snapshots_dir = Path(self._session_browse_dir)
        else:
            snapshots_dir = self._get_current_snapshots_dir()

        date_folders = self.controller.get_available_date_folders(snapshots_dir)

        if not date_folders:
            messagebox.showinfo("No Folders", f"No date folders found in {snapshots_dir}")
            return

        # Create selection dialog
        dialog = tk.Toplevel(self)
        dialog.title("Select Date Folder")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="Available date folders:", font=("Arial", 10, "bold")).pack(pady=10)

        # Listbox with scrollbar
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        for folder in date_folders:
            listbox.insert(tk.END, folder.name)

        def on_select():
            selection = listbox.curselection()
            if selection:
                selected_folder = date_folders[selection[0]]
                self.source_folder_entry.delete(0, tk.END)
                self.source_folder_entry.insert(0, str(selected_folder))
                self.scan_source_folder()
                dialog.destroy()

        ttk.Button(dialog, text="Select", command=on_select).pack(pady=5)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=5)

    def scan_source_folder(self):
        """Scan selected source folder"""
        folder_path = self.source_folder_entry.get()

        if not folder_path:
            return

        self.log_message(f"Scanning folder: {folder_path}")

        success, collection, message = self.controller.scan_folder(Path(folder_path))

        if success:
            self.current_collection = collection
            info_text = (
                f"Found: {collection.total_count} images | "
                f"Date Range: {collection.get_date_range_str()} | "
                f"Duration: {collection.get_duration_str()} | "
                f"Size: {collection.get_size_str()}"
            )
            self.image_info_label.configure(text=info_text, foreground="green")
            self.log_message(f"✓ {message}: {info_text}")
            self.update_estimates()

            # Auto-suggest output filename with full path based on date
            if collection.first_timestamp:
                date_str = collection.first_timestamp.strftime("%Y-%m-%d")
                suggested_name = f"timelapse-{date_str}.mp4"

                # Determine output directory
                # Priority: 1) Last used dir, 2) Parent of source folder, 3) Current directory
                if self.config_manager and self.config_manager.ui.last_video_export_dir:
                    output_dir = Path(self.config_manager.ui.last_video_export_dir)
                else:
                    # Use parent directory of source folder
                    output_dir = collection.source_folder.parent

                # Construct full path
                suggested_path = output_dir / suggested_name

                self.output_file_entry.delete(0, tk.END)
                self.output_file_entry.insert(0, str(suggested_path))
        else:
            self.current_collection = None
            self.image_info_label.configure(text=message, foreground="red")
            self.log_message(f"✗ {message}")

    def browse_output_file(self):
        """Browse for output file"""
        # Determine initial directory
        current_path = self.output_file_entry.get()
        if current_path and os.path.dirname(current_path):
            initial_dir = os.path.dirname(current_path)
            initial_file = os.path.basename(current_path)
        elif self.config_manager and self.config_manager.ui.last_video_export_dir:
            initial_dir = self.config_manager.ui.last_video_export_dir
            initial_file = f"timelapse.{self.format_var.get()}"
        else:
            initial_dir = os.getcwd()
            initial_file = f"timelapse.{self.format_var.get()}"

        filename = filedialog.asksaveasfilename(
            title="Save Video As",
            initialdir=initial_dir,
            initialfile=initial_file,
            defaultextension=f".{self.format_var.get()}",
            filetypes=[
                (f"{self.format_var.get().upper()} files", f"*.{self.format_var.get()}"),
                ("All files", "*.*")
            ]
        )

        if filename:
            self.output_file_entry.delete(0, tk.END)
            self.output_file_entry.insert(0, filename)

            # Save the directory for next time
            if self.config_manager:
                output_dir = os.path.dirname(filename)
                self.config_manager.ui.last_video_export_dir = output_dir

    def load_preset(self, event=None):
        """Load selected preset"""
        preset_name = self.preset_var.get()
        if not preset_name:
            return

        preset = self.preset_manager.get_preset(preset_name)
        if preset:
            self.framerate_var.set(preset.framerate)
            self.quality_var.set(preset.quality)
            self.speed_var.set(preset.speed_multiplier)
            self.resolution_var.set(preset.resolution)
            self.format_var.set(preset.format)
            self.add_timestamp_var.set(preset.add_timestamp)
            self.preserve_originals_var.set(preset.preserve_originals)
            self.open_when_done_var.set(preset.open_when_done)

            self.log_message(f"Loaded preset: {preset_name}")
            self.update_estimates()

            # Save as last used preset
            if self.config_manager:
                self.config_manager.ui.last_video_preset = preset_name
                self.config_manager.save_to_file()

    def save_as_preset(self):
        """Save current settings as preset"""
        # Ask for preset name
        dialog = tk.Toplevel(self)
        dialog.title("Save Preset")
        dialog.geometry("350x120")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="Preset Name:").pack(pady=(15, 5))

        name_entry = ttk.Entry(dialog, width=40)
        name_entry.pack(pady=5)
        name_entry.focus()

        def save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Please enter a preset name")
                return

            settings = self.get_current_settings()
            success, message = self.preset_manager.save_preset(name, settings)

            if success:
                # Refresh combo box
                self.preset_combo['values'] = self.preset_manager.list_presets()
                self.log_message(f"✓ Saved preset: {name}")
                dialog.destroy()
                messagebox.showinfo("Success", f"Preset '{name}' saved successfully")
            else:
                messagebox.showerror("Error", message)

        ttk.Button(dialog, text="Save", command=save).pack(pady=5)

    def manage_presets(self):
        """Open preset management dialog"""
        dialog = tk.Toplevel(self)
        dialog.title("Manage Presets")
        dialog.geometry("500x400")
        dialog.transient(self)

        ttk.Label(dialog, text="Custom Presets:", font=("Arial", 10, "bold")).pack(pady=10)

        # Listbox with custom presets
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        def refresh_list():
            listbox.delete(0, tk.END)
            for preset_name in self.preset_manager.list_presets(include_builtin=False):
                listbox.insert(tk.END, preset_name)

        refresh_list()

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        def delete_preset():
            selection = listbox.curselection()
            if not selection:
                messagebox.showinfo("No Selection", "Please select a preset to delete")
                return

            preset_name = listbox.get(selection[0])
            if messagebox.askyesno("Confirm Delete", f"Delete preset '{preset_name}'?"):
                success, message = self.preset_manager.delete_preset(preset_name)
                if success:
                    refresh_list()
                    self.preset_combo['values'] = self.preset_manager.list_presets()
                    self.log_message(f"✓ Deleted preset: {preset_name}")
                else:
                    messagebox.showerror("Error", message)

        ttk.Button(button_frame, text="Delete", command=delete_preset).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def get_current_settings(self) -> VideoExportSettings:
        """Get current settings from UI"""
        return VideoExportSettings(
            framerate=self.framerate_var.get(),
            quality=self.quality_var.get(),
            speed_multiplier=self.speed_var.get(),
            resolution=self.resolution_var.get(),
            format=self.format_var.get(),
            add_timestamp=self.add_timestamp_var.get(),
            preserve_originals=self.preserve_originals_var.get(),
            open_when_done=self.open_when_done_var.get()
        )

    def update_estimates(self):
        """Update estimated duration and file size"""
        if not self.current_collection:
            self.estimate_label.configure(text="Select folder first", foreground="gray")
            return

        try:
            # Estimate duration
            duration = self.controller.estimate_duration(
                self.current_collection.total_count,
                self.framerate_var.get(),
                self.speed_var.get()
            )

            # Estimate file size
            sample_image = self.current_collection.images[0] if self.current_collection.images else None
            filesize = self.controller.estimate_filesize(
                self.current_collection.total_count,
                self.resolution_var.get(),
                self.quality_var.get(),
                self.framerate_var.get(),
                sample_image
            )

            estimate_text = f"Duration: {duration:.1f}s | Size: ~{filesize:.1f} MB"
            self.estimate_label.configure(text=estimate_text, foreground="blue")

        except Exception as e:
            self.estimate_label.configure(text=f"Error: {str(e)}", foreground="red")

    def start_export(self):
        """Start video export"""
        # Validate inputs
        if not self.current_collection:
            messagebox.showerror("Error", "Please select a source folder first")
            return

        output_file = self.output_file_entry.get()
        if not output_file:
            messagebox.showerror("Error", "Please specify an output file")
            return

        # Check FFmpeg
        ffmpeg_ok, msg = self.controller.check_ffmpeg()
        if not ffmpeg_ok:
            messagebox.showerror("FFmpeg Not Found", msg)
            return

        # Prepare export
        settings = self.get_current_settings()
        output_path = Path(output_file)

        success, job, message = self.controller.prepare_export(settings, self.current_collection, output_path)

        if not success:
            messagebox.showerror("Export Preparation Failed", message)
            return

        # Confirm if output file exists
        if output_path.exists():
            if not messagebox.askyesno("Overwrite File", f"File '{output_file}' already exists. Overwrite?"):
                return

        # Update UI state
        self.is_exporting = True
        self.create_video_btn.configure(state=tk.DISABLED)
        self.cancel_btn.configure(state=tk.NORMAL)
        self.status_label.configure(text="Exporting...", foreground="blue")
        self.progress_bar['value'] = 0
        self.log_message("=" * 50)
        self.log_message("Starting video export...")

        # Start export in background thread
        self.controller.export_video_async(
            job=job,
            completion_callback=self.on_export_complete,
            progress_callback=self.on_export_progress,
            log_callback=self.log_message
        )

    def cancel_export(self):
        """Cancel ongoing export"""
        if messagebox.askyesno("Cancel Export", "Are you sure you want to cancel the export?"):
            self.controller.cancel_export()
            self.log_message("Cancelling export...")

    def on_export_progress(self, status: str, percent: float, info: Optional[ProgressInfo]):
        """Handle export progress updates"""
        def update_ui():
            self.status_label.configure(text=status)
            self.progress_bar['value'] = percent

            if info:
                details = f"Frame: {info.frame} | FPS: {info.fps:.1f} | Speed: {info.speed:.2f}x | Size: {info.size_kb}KB"
                self.progress_details_label.configure(text=details)

        # Update UI on main thread
        self.after(0, update_ui)

    def on_export_complete(self, result: ExportResult):
        """Handle export completion"""
        def update_ui():
            self.is_exporting = False
            self.create_video_btn.configure(state=tk.NORMAL)
            self.cancel_btn.configure(state=tk.DISABLED)
            self.progress_bar['value'] = 100 if result.success else 0

            if result.success:
                self.status_label.configure(text="Export Complete!", foreground="green")
                self.log_message("=" * 50)
                self.log_message(f"✓ {result.message}")
                self.log_message(f"Output: {result.output_file}")
                self.log_message(f"Size: {result.output_size_bytes / (1024*1024):.2f} MB")
                self.log_message("=" * 50)

                # Save the directory for next time
                if self.config_manager and result.output_file:
                    output_dir = str(result.output_file.parent)
                    self.config_manager.ui.last_video_export_dir = output_dir
                    # Save config to disk
                    self.config_manager.save_to_file("camera_config.json")

                # Open video if requested
                if self.open_when_done_var.get() and result.output_file:
                    os.startfile(str(result.output_file))

                messagebox.showinfo("Success", result.message)
            else:
                self.status_label.configure(text="Export Failed", foreground="red")
                self.log_message("=" * 50)
                self.log_message(f"✗ {result.message}")
                self.log_message("=" * 50)
                messagebox.showerror("Export Failed", result.message)

        # Update UI on main thread
        self.after(0, update_ui)

    def test_ffmpeg(self):
        """Test FFmpeg installation"""
        is_installed, version = self.ffmpeg_wrapper.check_installation()

        if is_installed:
            msg = f"FFmpeg is installed and working!\n\nVersion: {version}"
            self.log_message(f"✓ FFmpeg check: {version}")
            messagebox.showinfo("FFmpeg Test", msg)
        else:
            msg = (
                "FFmpeg not found!\n\n"
                "Please install FFmpeg:\n"
                "1. Download from: https://ffmpeg.org/download.html\n"
                "2. Add to system PATH, or\n"
                "3. Place ffmpeg.exe in the 'bin' folder"
            )
            self.log_message("✗ FFmpeg not found")
            messagebox.showerror("FFmpeg Not Found", msg)

    def check_ffmpeg_status(self):
        """Check FFmpeg status on startup"""
        is_installed, version = self.ffmpeg_wrapper.check_installation()

        if is_installed:
            self.log_message(f"✓ FFmpeg detected: {version}")
        else:
            self.log_message("✗ FFmpeg not found - video export will not work")
            self.log_message("  Install FFmpeg from: https://ffmpeg.org/download.html")

    def log_message(self, message: str):
        """Add message to log"""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def clear_log(self):
        """Clear log"""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def load_last_settings(self):
        """Load last used settings from config"""
        if self.config_manager:
            # Load last used preset
            last_preset = self.config_manager.ui.last_video_preset
            if last_preset and last_preset in self.preset_manager.list_presets():
                self.preset_var.set(last_preset)
                self.load_preset()

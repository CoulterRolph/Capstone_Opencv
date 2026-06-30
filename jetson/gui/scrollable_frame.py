# gui/scrollable_frame.py

"""
Scrollable frame helper for Tkinter.

Provides a reusable scrollable container for content that may exceed
the available vertical space on smaller displays (e.g., 1024x768).
"""

import tkinter as tk
from tkinter import ttk


class ScrollableFrame(tk.Frame):
    """
    A Frame that contains a scrollable canvas with an inner frame.
    
    Allows content to overflow vertically with mousewheel/scrollbar support
    on screens with limited vertical space (e.g., 1024x768).
    
    Usage:
        scrollable = ScrollableFrame(parent, bg="white")
        scrollable.pack(fill="both", expand=True)
        
        # Add widgets to scrollable.inner_frame instead of scrollable
        tk.Label(scrollable.inner_frame, text="Content").pack()
    """
    
    def __init__(self, parent, **kwargs):
        """
        Initialize the scrollable frame.
        
        Args:
            parent: Parent Tkinter widget.
            **kwargs: Additional frame kwargs (bg, etc.).
        """
        super().__init__(parent, **kwargs)
        
        # Create canvas and scrollbar
        self.canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        self.inner_frame = tk.Frame(self, **kwargs)
        
        # Configure canvas
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Create window in canvas
        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.inner_frame,
            anchor="nw",
        )
        
        # Bind canvas resize to update inner frame width
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        # Bind mousewheel for scrolling
        self.inner_frame.bind("<MouseWheel>", self._on_mousewheel)
        self.inner_frame.bind("<Button-4>", self._on_mousewheel)
        self.inner_frame.bind("<Button-5>", self._on_mousewheel)
        
        # Update scroll region when inner frame changes
        self.inner_frame.bind("<Configure>", self._on_inner_frame_configure)
        
    def _on_canvas_configure(self, event):
        """
        Resize inner frame to match canvas width.
        """
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        
    def _on_inner_frame_configure(self, event):
        """
        Update canvas scroll region when inner frame size changes.
        """
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
    def _on_mousewheel(self, event):
        """
        Handle mousewheel scroll events.
        """
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(3, "units")
        else:
            self.canvas.yview_scroll(-3, "units")

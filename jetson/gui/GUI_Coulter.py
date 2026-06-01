import tkinter as tk


class TCubedGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("T-Cubed Ping Pong Training System")
        self.root.geometry("1024x768")
        self.root.resizable(False, False)

        self.bg_color = "#1f2933"
        self.panel_color = "#2f3e4e"
        self.display_color = "#f4f6f8"

        self.root.configure(bg=self.bg_color)

        self.speed = tk.IntVar(value=50)
        self.shot_count = tk.IntVar(value=10)
        self.shot_delay = tk.DoubleVar(value=1.5)

        self.show_main_screen()

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def make_button(self, parent, text, color, command):
        return tk.Button(
            parent,
            text=text,
            font=("Arial", 15, "bold"),
            bg=color,
            fg="white",
            activebackground=color,
            activeforeground="white",
            bd=0,
            relief="flat",
            height=2,
            cursor="hand2",
            command=command
        )

    def set_status(self, text):
        self.status_label.config(text=f"Status: {text}")

    def start_pressed(self):
        self.set_status("System started")

    def stop_pressed(self):
        self.set_status("System stopped")

    def visual_pressed(self):
        self.show_visual_screen()

    def save_settings(self):
        print("Settings saved:")
        print(f"Speed: {self.speed.get()}%")
        print(f"Amount of Shots: {self.shot_count.get()}")
        print(f"Time Between Shots: {self.shot_delay.get()} seconds")

    def create_header(self, title, subtitle):
        header = tk.Frame(self.root, bg=self.bg_color)
        header.pack(fill="x", padx=30, pady=(20, 10))

        tk.Label(
            header,
            text=title,
            font=("Arial", 30, "bold"),
            bg=self.bg_color,
            fg="white"
        ).pack(anchor="w")

        tk.Label(
            header,
            text=subtitle,
            font=("Arial", 13),
            bg=self.bg_color,
            fg="#b8c7d9"
        ).pack(anchor="w", pady=(3, 0))

    def create_display(self, title, description):
        display_frame = tk.Frame(self.root, bg=self.display_color)
        display_frame.pack(padx=30, pady=(5, 15), fill="both", expand=True)

        tk.Label(
            display_frame,
            text=title,
            font=("Arial", 24, "bold"),
            bg=self.display_color,
            fg="#1f2933"
        ).pack(pady=(120, 10))

        tk.Label(
            display_frame,
            text=description,
            font=("Arial", 16),
            bg=self.display_color,
            fg="#4b5563",
            justify="center"
        ).pack()

    def create_bottom_panel(self):
        bottom_panel = tk.Frame(self.root, bg=self.panel_color)
        bottom_panel.pack(fill="x", padx=30, pady=(0, 25))

        self.status_label = tk.Label(
            bottom_panel,
            text="Status: Idle",
            font=("Arial", 12),
            bg=self.panel_color,
            fg="#d9e2ec"
        )
        self.status_label.pack(anchor="w", padx=15, pady=(10, 0))

        button_frame = tk.Frame(bottom_panel, bg=self.panel_color)
        button_frame.pack(fill="x", padx=10, pady=12)

        for col in range(4):
            button_frame.columnconfigure(col, weight=1)

        return button_frame

    def show_main_screen(self):
        self.clear_screen()

        self.create_header(
            "T-Cubed Training System",
            "Setup and control screen"
        )

        self.create_display(
            "Camera / System Display",
            "Live camera feed, shooter status, and setup preview will appear here."
        )

        button_frame = self.create_bottom_panel()

        self.make_button(
            button_frame, "Start", "#28a745", self.start_pressed
        ).grid(row=0, column=0, padx=8, sticky="ew")

        self.make_button(
            button_frame, "Stop", "#dc3545", self.stop_pressed
        ).grid(row=0, column=1, padx=8, sticky="ew")

        self.make_button(
            button_frame, "Settings", "#007bff", self.show_settings_screen
        ).grid(row=0, column=2, padx=8, sticky="ew")

        self.make_button(
            button_frame, "Visual Feedback", "#6f42c1", self.visual_pressed
        ).grid(row=0, column=3, padx=8, sticky="ew")

    def show_settings_screen(self):
        self.clear_screen()

        self.create_header(
            "T-Cubed Shooter Settings",
            "Configure the ball shooter before starting a drill"
        )

        settings_frame = tk.Frame(self.root, bg=self.display_color)
        settings_frame.pack(padx=30, pady=(5, 15), fill="both", expand=True)

        slider_panel = tk.Frame(settings_frame, bg=self.display_color)
        slider_panel.pack(expand=True, fill="both", padx=80, pady=40)

        self.create_slider(
            slider_panel,
            "Shooter Speed (%)",
            self.speed,
            0,
            100
        )

        self.create_slider(
            slider_panel,
            "Amount of Shots",
            self.shot_count,
            1,
            50
        )

        self.create_slider(
            slider_panel,
            "Time Between Shots (seconds)",
            self.shot_delay,
            0.5,
            10,
            resolution=0.5
        )

        button_frame = self.create_bottom_panel()

        self.make_button(
            button_frame, "Save Settings", "#28a745", self.save_settings
        ).grid(row=0, column=0, padx=8, sticky="ew")

        self.make_button(
            button_frame, "Back to Setup", "#6c757d", self.show_main_screen
        ).grid(row=0, column=1, padx=8, sticky="ew")

    def create_slider(self, parent, label_text, variable, from_value, to_value, resolution=1):
        frame = tk.Frame(parent, bg=self.display_color)
        frame.pack(fill="x", pady=22)

        tk.Label(
            frame,
            text=label_text,
            font=("Arial", 18, "bold"),
            bg=self.display_color,
            fg="#1f2933"
        ).pack(anchor="w")

        slider = tk.Scale(
            frame,
            from_=from_value,
            to=to_value,
            orient="horizontal",
            variable=variable,
            resolution=resolution,
            length=760,
            font=("Arial", 12),
            bg=self.display_color,
            fg="#1f2933",
            troughcolor="#cbd5e1",
            highlightthickness=0
        )
        slider.pack(anchor="w", pady=(8, 0))

    def show_visual_screen(self):
        self.clear_screen()

        self.create_header(
            "T-Cubed Visual Feedback",
            "Shot analysis and player feedback screen"
        )

        self.create_display(
            "Feedback Display",
            "Heat maps, ball trajectory, bounce locations, and shot statistics will appear here."
        )

        button_frame = self.create_bottom_panel()

        self.make_button(
            button_frame, "Heat Map", "#f0ad4e", lambda: self.set_status("Heat map selected")
        ).grid(row=0, column=0, padx=8, sticky="ew")

        self.make_button(
            button_frame, "Analyze", "#17a2b8", lambda: self.set_status("Analyze selected")
        ).grid(row=0, column=1, padx=8, sticky="ew")

        self.make_button(
            button_frame, "Stats", "#20c997", lambda: self.set_status("Stats selected")
        ).grid(row=0, column=2, padx=8, sticky="ew")

        self.make_button(
            button_frame, "Back to Setup", "#6c757d", self.show_main_screen
        ).grid(row=0, column=3, padx=8, sticky="ew")


if __name__ == "__main__":
    root = tk.Tk()
    app = TCubedGUI(root)
    root.mainloop()
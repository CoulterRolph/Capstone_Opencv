# gui/page_manager.py

"""
Page manager for the Tkinter GUI.

This file is responsible for:
- Registering page frames
- Hiding the current page
- Showing the selected page

It does not know the internal details of each page.
"""


# ============================================================
# Page manager
# ============================================================

class PageManager:
    """
    Small helper class for switching between Tkinter pages.
    """

    def __init__(self, container):
        """
        Create a page manager.

        Args:
            container:
                The parent Tkinter frame where pages will be placed.
        """

        self.container = container
        self.pages = {}
        self.current_page_name = None

    def register_page(self, page_name, page_frame):
        """
        Register a page with the manager.

        Args:
            page_name:
                String name used to identify the page.

            page_frame:
                Tkinter Frame object for the page.
        """

        self.pages[page_name] = page_frame

    def show_page(self, page_name):
        """
        Show one page and hide the previously visible page.
        """

        if page_name not in self.pages:
            raise KeyError(f"Page is not registered: {page_name}")

        if self.current_page_name is not None:
            current_page = self.pages[self.current_page_name]
            current_page.pack_forget()

        next_page = self.pages[page_name]

        next_page.pack(
            fill="both",
            expand=True,
        )

        self.current_page_name = page_name

    def get_current_page_name(self):
        """
        Return the name of the currently visible page.
        """

        return self.current_page_name


# ============================================================
# Direct test
# ============================================================

def test_page_manager_direct():
    """
    Direct test for PageManager.

    This creates two simple pages and switches between them.
    """

    import tkinter as tk

    root = tk.Tk()
    root.title("PageManager Direct Test")
    root.geometry("400x250")

    container = tk.Frame(root)
    container.pack(
        fill="both",
        expand=True,
    )

    page_manager = PageManager(
        container=container,
    )

    page_one = tk.Frame(container)
    page_two = tk.Frame(container)

    tk.Label(
        page_one,
        text="Page One",
        font=("Arial", 16, "bold"),
    ).pack(pady=20)

    tk.Button(
        page_one,
        text="Go to Page Two",
        command=lambda: page_manager.show_page("page_two"),
    ).pack(pady=10)

    tk.Label(
        page_two,
        text="Page Two",
        font=("Arial", 16, "bold"),
    ).pack(pady=20)

    tk.Button(
        page_two,
        text="Go to Page One",
        command=lambda: page_manager.show_page("page_one"),
    ).pack(pady=10)

    page_manager.register_page(
        "page_one",
        page_one,
    )

    page_manager.register_page(
        "page_two",
        page_two,
    )

    page_manager.show_page(
        "page_one",
    )

    root.mainloop()


if __name__ == "__main__":
    test_page_manager_direct()
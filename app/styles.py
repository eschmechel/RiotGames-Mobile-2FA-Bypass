import os


def load_stylesheet():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "assets", "style.qss")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""

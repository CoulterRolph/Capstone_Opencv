from pathlib import Path
from datetime import datetime

# ======================
# CONFIG (edit these)
# ======================
DIRECTORY = r"C:\\Users\\diplo\\Pictures\\Camera Roll\\training_ball"
PREFIX = "ball_player"  # e.g. "webcam", "session1", etc.

# Use today's date automatically (YYYYMMDD). Or set manually like "20260304".
DATE_STR = datetime.now().strftime("%Y%m%d")

# Rename only certain file types (set to None to rename all files)
EXTENSIONS = {".jpg", ".png", ".mp4", ".mov"}  # <- edit
# EXTENSIONS = None  # <- uncomment to rename all files

# Starting index + padding width (0001, 0002, ...)
START_INDEX = 1
PAD_WIDTH = 3

# Safety: if True, prints changes without renaming
DRY_RUN = False
# ======================


def should_rename(p: Path) -> bool:
    if not p.is_file():
        return False
    if EXTENSIONS is None:
        return True
    return p.suffix.lower() in {e.lower() for e in EXTENSIONS}


def main():
    folder = Path(DIRECTORY)
    if not folder.exists() or not folder.is_dir():
        raise ValueError(f"Not a valid directory: {folder}")

    files = sorted([p for p in folder.iterdir() if should_rename(p)], key=lambda x: x.name.lower())

    if not files:
        print("No matching files found.")
        return

    # Build all new names first (prevents partial rename mess)
    planned = []
    for i, p in enumerate(files, start=START_INDEX):
        new_name = f"{PREFIX}_{DATE_STR}_{i:0{PAD_WIDTH}d}{p.suffix.lower()}"
        planned.append((p, folder / new_name))

    # Collision check
    targets = [dst.name for _, dst in planned]
    if len(targets) != len(set(targets)):
        raise RuntimeError("Generated duplicate target names. Adjust PAD_WIDTH/START_INDEX.")

    existing = {p.name for p in folder.iterdir()}
    collisions = [dst for _, dst in planned if dst.name in existing and dst not in [src for src, _ in planned]]
    if collisions:
        print("Name collision(s) detected. These targets already exist:")
        for c in collisions:
            print("  ", c.name)
        print("Aborting.")
        return

    # Show plan
    print(f"Planned renames in: {folder}")
    for src, dst in planned:
        print(f"  {src.name}  ->  {dst.name}")

    if DRY_RUN:
        print("\nDRY_RUN=True, no files were renamed.")
        print("Set DRY_RUN=False to actually rename.")
        return

    # Execute
    for src, dst in planned:
        src.rename(dst)

    print("\nDone.")


if __name__ == "__main__":
    main()
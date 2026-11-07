import os
import re

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

SCAN_FOLDERS = ["api", "ui"]  # Add more folders as needed
INI_FILE = os.path.join(PROJECT_ROOT, "pytest.ini")
OUTPUT_FILE = os.path.join(CURRENT_DIR, "pytest_markers_output.txt")


def find_used_markers(base_dirs):
    marker_pattern = re.compile(r'@pytest\.mark\.([a-zA-Z_][a-zA-Z0-9_]*)')
    markers = set()

    for folder in base_dirs:
        folder_path = os.path.join(PROJECT_ROOT, folder)
        if not os.path.exists(folder_path):
            continue
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    try:
                        with open(full_path, encoding="utf-8") as f:
                            found = marker_pattern.findall(f.read())
                            markers.update(found)
                    except Exception as e:
                        print(f"⚠️ Error reading {full_path}: {e}")
    return markers


def read_existing_ini_markers(ini_path):
    if not os.path.exists(ini_path):
        return set()

    existing = set()
    inside_marker_block = False

    with open(ini_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()

            if stripped.startswith("markers") and "=" in stripped:
                inside_marker_block = True
                parts = stripped.split("=", 1)
                marker_part = parts[1].strip()
                if ":" in marker_part:
                    marker_name = marker_part.split(":", 1)[0].strip()
                    existing.add(marker_name)

            elif inside_marker_block and (line.startswith(" ") or line.startswith("\t")):
                if ":" in stripped:
                    marker_name = stripped.split(":", 1)[0].strip()
                    existing.add(marker_name)
            elif inside_marker_block:
                break  # End of marker block

    return existing


if __name__ == "__main__":
    print("🔍 Scanning for pytest markers...")

    used_markers = find_used_markers(SCAN_FOLDERS)
    existing_markers = read_existing_ini_markers(INI_FILE)

    new_markers = sorted(used_markers - existing_markers)

    if not new_markers:
        print("✅ No new markers to add.")
    else:
        print(f"🆕 {len(new_markers)} new markers found.")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("# Paste the below lines into the [pytest] section of pytest.ini\n\n")
            f.write("markers =\n")
            for marker in new_markers:
                f.write(f"    {marker}: auto-detected marker\n")

        print(f"📄 Saved to: {OUTPUT_FILE}")

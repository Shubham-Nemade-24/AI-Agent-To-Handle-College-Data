import os
import shutil

# === CONFIG ===
CHROMA_DIRS = [
    "chroma",         # default persist directory
    ".chroma",        # sometimes auto-created by older versions
    "chroma_index",   # extra index folder (optional, but safe to delete)
]


def delete_folder(path):
    """Delete a folder if it exists."""
    if os.path.exists(path) and os.path.isdir(path):
        shutil.rmtree(path)
        print(f"🗑️ Deleted folder: {path}")
    else:
        print(f"⚠️ Folder not found (skip): {path}")


def delete_file(path):
    """Delete a file if it exists."""
    if os.path.exists(path) and os.path.isfile(path):
        os.remove(path)
        print(f"🗑️ Deleted file: {path}")
    else:
        print(f"⚠️ File not found (skip): {path}")


if __name__ == "__main__":
    print("🚨 RESETTING CHROMA VECTOR DATABASE...")
    print("This will delete ALL embeddings, metadata, and indexes.\n")

    # delete all chroma directories
    for path in CHROMA_DIRS:
        delete_folder(path)

    print("\n✅ RESET COMPLETE")
    print("Your vector DB is now empty. You can re-run your Streamlit app or populate_database.py.")
import os
import shutil

# === CONFIG ===
CHROMA_DIR = "chroma"             # your Chroma DB folder (modify if different)
PROCESSED_JSON = "processed.json" # file tracking processed PDFs

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
    print("🚨 Resetting vector DB and metadata...")

    # Delete Chroma DB storage
    delete_folder(CHROMA_DIR)

    # Delete processed.json
    delete_file(PROCESSED_JSON)

    print("\n✅ Reset complete. You can now run populate_database.py again.")
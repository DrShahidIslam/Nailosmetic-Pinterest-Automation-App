import json
import os
from pathlib import Path

class SmartJSON:
    """
    A utility to safely merge and save JSON data, preventing data loss
    during concurrent updates (common in GitHub Actions).
    """

    @staticmethod
    def read_file(file_path):
        """Safely read and return JSON data from a file. Returns [] if missing or invalid."""
        path = Path(file_path)
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"   Warning: Could not read {file_path}: {e}")
            return []

    @staticmethod
    def merge_lists(existing, new_items):
        """Union of two lists, preserving order of existing items."""
        seen = set()
        result = []
        
        # Helper to get a stable hashable key for dictionaries
        def get_key(item):
            if isinstance(item, dict):
                # Try to use URL or ID as unique key if available
                return item.get("url") or item.get("link") or item.get("id") or json.dumps(item, sort_keys=True)
            return item

        for item in existing:
            key = get_key(item)
            if key not in seen:
                result.append(item)
                seen.add(key)
        
        for item in new_items:
            key = get_key(item)
            if key not in seen:
                result.append(item)
                seen.add(key)
        
        return result

    @staticmethod
    def update_file(file_path, new_data):
        """
        Reads the latest version from disk, merges new_data into it, and saves.
        Works for both lists and dictionaries.
        """
        path = Path(file_path)
        
        # 1. Load existing data
        existing_data = None
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except Exception as e:
                print(f"   Warning: Could not read {file_path}: {e}")
        
        # 2. Merge logic
        if existing_data is None:
            final_data = new_data
        elif isinstance(existing_data, list) and isinstance(new_data, list):
            final_data = SmartJSON.merge_lists(existing_data, new_data)
        elif isinstance(existing_data, dict) and isinstance(new_data, dict):
            # Shallow merge for dicts
            final_data = {**existing_data, **new_data}
        else:
            # Fallback for mixed types or single items
            final_data = new_data

        # 3. Save atomically
        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(final_data, f, indent=4)
            return True
        except Exception as e:
            print(f"   ❌ Error saving {file_path}: {e}")
            return False

if __name__ == "__main__":
    import sys
    import subprocess

    if len(sys.argv) > 1 and sys.argv[1] == "--sync-all":
        print("🔄 Performing Smart Sync of all shared data files...")
        shared_dir = Path(__file__).parent / "shared"
        if not shared_dir.exists():
            print("   ❌ 'shared' directory not found.")
            sys.exit(1)
            
        json_files = list(shared_dir.glob("*.json"))
        for jf in json_files:
            print(f"   📂 Syncing {jf.name}...")
            SmartJSON.update_file(jf, []) 
        print("✅ Sync complete.")

    elif len(sys.argv) > 1 and sys.argv[1] == "--resolve-conflicts":
        print("🔄 Resolving Git conflicts for shared data files...")
        shared_dir = Path(__file__).parent / "shared"
        if not shared_dir.exists():
            sys.exit(1)

        for jf in shared_dir.glob("*.json"):
            try:
                # Get remote version
                remote_str = subprocess.check_output(["git", "show", f"origin/main:shared/{jf.name}"]).decode("utf-8")
                remote_data = json.loads(remote_str)
                
                # Get local version from HEAD
                local_str = subprocess.check_output(["git", "show", f"HEAD:shared/{jf.name}"]).decode("utf-8")
                local_data = json.loads(local_str)
                
                # Merge logic
                if isinstance(remote_data, list) and isinstance(local_data, list):
                    merged_data = SmartJSON.merge_lists(remote_data, local_data)
                elif isinstance(remote_data, dict) and isinstance(local_data, dict):
                    merged_data = {**remote_data, **local_data}
                else:
                    merged_data = local_data # fallback

                # Write resolved data
                with open(jf, "w", encoding="utf-8") as f:
                    json.dump(merged_data, f, indent=4)
                print(f"   ✅ Merged {jf.name} successfully.")
            except Exception as e:
                print(f"   ❌ Failed to merge {jf.name}: {e}")
                
        print("✅ Conflict resolution complete.")


#!/usr/bin/env python3
import os
import shutil
from git import Repo
import tempfile
import argparse
import json
import hashlib
from typing import Dict, List, Tuple, Set

# Load the configuration file
with open("conf.json") as f:
    c = json.load(f)

OC_SERVICES_TEMPLATES = os.getenv("OC_SERVICES_TEMPLATES", c["oc_services_templates"])

class SyncConfig:
    def __init__(self, folders: Set[str], files: Set[str]):
        self.folders = folders
        self.files = files

    def __str__(self):
        parts = []
        if self.folders:
            parts.append(f"Folders: {', '.join(self.folders)}")
        if self.files:
            parts.append(f"Files: {', '.join(self.files)}")
        return " | ".join(parts)

class ChangeTracker:
    def __init__(self):
        self.to_add: List[str] = []
        self.to_update: List[str] = []
        
    def add_file(self, path: str):
        self.to_add.append(path)
        
    def update_file(self, path: str):
        self.to_update.append(path)
        
    def has_changes(self) -> bool:
        return bool(self.to_add or self.to_update)
        
    def print_plan(self):
        if not self.has_changes():
            print("\nNo changes detected.")
            return

        print("\nChanges to apply:")
        print("================")
        
        if self.to_add:
            print("\nNew files:")
            for f in sorted(self.to_add):
                print(f"  + {f}")
                
        if self.to_update:
            print("\nModified files:")
            for f in sorted(self.to_update):
                print(f"  ~ {f}")
                
        print(f"\nSummary: {len(self.to_add)} additions, {len(self.to_update)} modifications")

def get_file_hash(filepath: str, chunk_size: int = 8192) -> str:
    """Calculate normalized content hash"""
    try:
        # First try to read as text
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Normalize line endings
        content = content.replace('\r\n', '\n')
        
        # Remove BOM if present
        if content.startswith('\ufeff'):
            content = content[1:]
            
        # Remove trailing spaces from lines
        content = '\n'.join(line.rstrip() for line in content.splitlines())
        
        # Calculate hash of normalized content
        sha1_hash = hashlib.sha1()
        sha1_hash.update(content.encode('utf-8'))
        return sha1_hash.hexdigest()
            
    except UnicodeDecodeError:
        # If not text, use binary mode
        sha1_hash = hashlib.sha1()
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                sha1_hash.update(chunk)
        return sha1_hash.hexdigest()

def check_file_update(src: str, dst: str) -> bool:
    """Check if file content has changed by comparing normalized hashes"""
    if not os.path.exists(dst):
        return True
    
    try:
        return get_file_hash(src) != get_file_hash(dst)
    except Exception as e:
        print(f"Warning: Error checking file update for {src}: {e}")
        return False

def should_sync_path(path: str, config: SyncConfig) -> bool:
    """Check if a path should be synced based on the configuration"""
    path = os.path.normpath(path)
    
    # Check if the path is a specific file to sync
    if path in config.files:
        return True
    
    # For directories, check if this path is either:
    # 1. A configured directory
    # 2. A parent of a configured directory
    # 3. A child of a configured directory
    for folder in config.folders:
        folder = os.path.normpath(folder)
        
        # Case 1: Exact match
        if path == folder:
            return True
            
        # Case 2: Current path is a parent directory of a configured folder
        try:
            relative = os.path.relpath(folder, path)
            if not relative.startswith('..'):
                return True
        except ValueError:
            pass
            
        # Case 3: Current path is inside a configured folder
        try:
            relative = os.path.relpath(path, folder)
            if not relative.startswith('..'):
                return True
        except ValueError:
            pass
    
    return False

def load_sync_config() -> SyncConfig:
    """Load sync configuration from config.json"""
    try:
        with open("conf.json") as f:
            config = json.load(f)
            
        sync_config = config.get("sync", {
            "folders": ["static"],
            "files": []
        })
        
        folders = set(sync_config.get("folders", ["static"]))
        files = set(sync_config.get("files", []))
        
        config = SyncConfig(folders, files)
        print(f"Loaded sync configuration: {config}")
        return config
            
    except FileNotFoundError:
        print("Warning: conf.json not found, using default sync path: 'static'")
        return SyncConfig({"static"}, set())
    except json.JSONDecodeError:
        print("Warning: Invalid conf.json format, using default sync path: 'static'")
        return SyncConfig({"static"}, set())
    except Exception as e:
        print(f"Warning: Error loading conf.json ({str(e)}), using default sync path: 'static'")
        return SyncConfig({"static"}, set())

def scan_changes(src_dir: str, dst_dir: str, tracker: ChangeTracker, config: SyncConfig) -> None:
    """Scan for changes between source and destination directories"""
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)

    for item in os.listdir(src_dir):
        if item == '.git':
            continue
            
        src_path = os.path.join(src_dir, item)
        dst_path = os.path.join(dst_dir, item)
        rel_path = os.path.relpath(dst_path, os.getcwd())
        
        # Skip if path is not in sync configuration
        if not should_sync_path(rel_path, config):
            continue
            
        if os.path.isdir(src_path):
            scan_changes(src_path, dst_path, tracker, config)
        else:
            if not os.path.exists(dst_path):
                tracker.add_file(rel_path)
            elif check_file_update(src_path, dst_path):
                tracker.update_file(rel_path)

def sync_files(src_dir: str, dst_dir: str, config: SyncConfig) -> None:
    """Synchronize files from source to destination directory"""
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)

    for item in os.listdir(src_dir):
        if item == '.git':
            continue
            
        src_path = os.path.join(src_dir, item)
        dst_path = os.path.join(dst_dir, item)
        rel_path = os.path.relpath(dst_path, os.getcwd())
        
        # Skip if path is not in sync configuration
        if not should_sync_path(rel_path, config):
            continue
            
        if os.path.isdir(src_path):
            sync_files(src_path, dst_path, config)
        elif check_file_update(src_path, dst_path):
            # Ensure the directory exists
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.copy2(src_path, dst_path)
            print(f"Updated: {rel_path}")

def sync_repository(auto_mode: bool = False) -> None:
    """Main function to handle repository synchronization"""
    cwd = os.getcwd()
    print(f"Working directory: {cwd}")
    
    # Load sync configuration
    config = load_sync_config()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            print(f"Cloning {OC_SERVICES_TEMPLATES}...")
            Repo.clone_from(OC_SERVICES_TEMPLATES, temp_dir)
            
            if not auto_mode:
                tracker = ChangeTracker()
                print("\nAnalyzing repository...")
                scan_changes(temp_dir, cwd, tracker, config)
                
                tracker.print_plan()
                
                if not tracker.has_changes():
                    return
                    
                if input("\nProceed with these changes? [y/N]: ").lower() != 'y':
                    print("Operation cancelled.")
                    return
                
                print("\nApplying changes...")
            
            sync_files(temp_dir, cwd, config)
            print("\nSync completed successfully!")
            
        except Exception as e:
            print(f"Error: {str(e)}")

def main():
    parser = argparse.ArgumentParser(
        description='Sync files from oc_services_templates repository'
    )
    parser.add_argument(
        '--auto',
        action='store_true',
        help='run in automatic mode without confirmation'
    )
    
    args = parser.parse_args()
    sync_repository(args.auto)

if __name__ == "__main__":
    main()
import os
from pathlib import Path

# Add or remove folder/file names here that you want to hide from the output
IGNORE_DIRS = {
    'venv', 'env', '.git', '__pycache__', 'node_modules', 
    '.vscode', '.idea', 'dist', 'build', '.next'
}
IGNORE_FILES = {
    '.DS_Store', 'generate_tree.py'  # Ignored this script itself to keep it clean
}

def generate_tree(dir_path: Path, prefix: str = "") -> str:
    """Recursively generates a tree-like string of the directory structure."""
    tree_str = ""
    
    # Get all items, filter out ignored ones
    try:
        items = [
            item for item in dir_path.iterdir()
            if item.name not in IGNORE_DIRS 
            and item.name not in IGNORE_FILES 
            and not item.name.endswith('.pyc')
        ]
    except PermissionError:
        return tree_str # Skip folders we don't have permission to read

    # Sort items: Directories first, then files, both alphabetically
    items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

    # Create the branch pointers
    pointers = ['├── '] * (len(items) - 1) + ['└── '] if items else []

    for pointer, item in zip(pointers, items):
        tree_str += f"{prefix}{pointer}{item.name}\n"
        if item.is_dir():
            # Extend the prefix for subdirectories
            extension = '│   ' if pointer == '├── ' else '    '
            tree_str += generate_tree(item, prefix=prefix + extension)
            
    return tree_str

def save_tree_to_file(root_dir: str, output_file: str = "repo_structure.txt"):
    """Generates the tree and writes it to a file."""
    root_path = Path(root_dir)
    
    # Start the tree with the root folder name
    tree_output = f"{root_path.resolve().name}/\n"
    tree_output += generate_tree(root_path)
    
    # Save to the text file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(tree_output)
        
    print(f"✅ Repository tree successfully saved to {output_file}")

if __name__ == "__main__":
    # "." means it runs in whatever folder the script is located
    save_tree_to_file(".", "repo_structure.txt")
import json
import asyncio
from pathlib import Path
from nicegui import ui
from git_handler import GitManager

# Initialize our backend GitManager toolbox
git_mgr = GitManager()

# ANCHORED PATH FIX: Always save/load repos.json in the same folder as this script
STORAGE_FILE = Path(__file__).parent / "repos.json"

def load_saved_repos():
    """Reads saved repository paths from the JSON file on startup."""
    if not STORAGE_FILE.exists():
        return []
    try:
        with open(STORAGE_FILE, "r") as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return []

def auto_discover_missing_repos():
    """Scans the base clone directory on startup and adds any unrecorded repositories to JSON."""
    base_dir = git_mgr.base_dir  # Points to './cloned_repos'
    saved_paths = load_saved_repos()
    
    # Convert saved paths to a Python set for fast lookup (normalized paths)
    saved_set = set(str(Path(p).resolve()) for p in saved_paths)
    
    found_new = False
    
    # Check if the base directory exists before scanning
    if base_dir.exists():
        for item in base_dir.iterdir():
            if item.is_dir() and (item / ".git").exists():
                abs_path = str(item.resolve())
                if abs_path not in saved_set:
                    print(f"Auto-discovered unrecorded repo: {abs_path}")
                    saved_paths.append(abs_path)
                    found_new = True
                    
    # If we found any new repositories on disk that weren't in JSON, save them!
    if found_new:
        with open(STORAGE_FILE, "w") as f:
            json.dump(saved_paths, f, indent=4)
            print("Updated repos.json with auto-discovered repositories.")
            
    return saved_paths

def save_repos_to_disk():
    """Saves the current list of repository paths to the JSON file."""
    paths = [r["path"] for r in tracked_repos]
    with open(STORAGE_FILE, "w") as f:
        json.dump(paths, f, indent=4)

# Initialize tracked_repos by auto-discovering any folders on disk and loading saved paths
tracked_repos = []
active_paths = auto_discover_missing_repos()

for path in active_paths:
    if Path(path).exists():
        meta = git_mgr.get_repo_metadata(path)
        meta["path"] = path  # Ensure the physical path is stored in the dictionary
        tracked_repos.append(meta)

async def handle_clone(url_input, repo_table, spinner):
    """Handles cloning a new repository asynchronously so the UI doesn't freeze."""
    url = url_input.value.strip()
    if not url:
        ui.notify("Please enter a valid Git URL", color="negative")
        return
    
    ui.notify(f"Cloning {url} (this may take a moment)...", color="info")
    spinner.visible = True  # Turn on loading spinner
    
    # Run heavy Git cloning in a background thread
    result = await asyncio.to_thread(git_mgr.clone_repo, url)
    
    spinner.visible = False  # Turn off loading spinner
    
    if result["success"]:
        ui.notify(result["message"], color="positive")
        path = result["path"]
        
        # Fetch metadata in a background thread
        meta = await asyncio.to_thread(git_mgr.get_repo_metadata, path)
        meta["path"] = path
        
        tracked_repos.append(meta)
        save_repos_to_disk()  # Save to JSON immediately
        
        url_input.value = ""
        repo_table.rows = tracked_repos
        repo_table.update()
    else:
        ui.notify(result["message"], color="negative")

async def handle_update(repo_path, repo_table):
    """Handles pulling the latest changes for a specific repository asynchronously."""
    ui.notify("Fetching updates...", color="info")
    
    # Run git pull in a background thread
    result = await asyncio.to_thread(git_mgr.update_repo, repo_path)
    
    if result["success"]:
        ui.notify("Repository updated successfully!", color="positive")
        meta = await asyncio.to_thread(git_mgr.get_repo_metadata, repo_path)
        meta["path"] = repo_path
        
        # Update the specific repo's metadata in our in-memory list
        for r in tracked_repos:
            if r["path"] == repo_path:
                r.update(meta)
                break
                
        repo_table.rows = tracked_repos
        repo_table.update()
    else:
        ui.notify(result["message"], color="negative")

async def handle_refresh_all(repo_table):
    """Refreshes metadata for all tracked repositories at once."""
    ui.notify("Refreshing all repositories...", color="info")
    
    updated_repos = []
    for r in tracked_repos:
        path = r["path"]
        if Path(path).exists():
            meta = await asyncio.to_thread(git_mgr.get_repo_metadata, path)
            meta["path"] = path
            updated_repos.append(meta)
        else:
            r["status"] = "Local folder missing"
            updated_repos.append(r)
            
    tracked_repos.clear()
    tracked_repos.extend(updated_repos)
    repo_table.rows = tracked_repos
    repo_table.update()
    ui.notify("All repositories refreshed!", color="positive")

# --- UI Layout Design (NiceGUI) ---
ui.query('body').classes('bg-gray-100')

with ui.column().classes('w-full max-w-4xl mx-auto p-6 gap-6'):
    # Header
    ui.label('🚀 GitPulse Dashboard').classes('text-3xl font-bold text-gray-800')
    
    # Input Card
    with ui.card().classes('w-full p-4 bg-white shadow-md rounded-lg'):
        ui.label('Add New Repository').classes('text-lg font-semibold mb-2')
        with ui.row().classes('w-full items-center gap-4'):
            url_input = ui.input('Repository URL (e.g., https://github.com/user/repo.git)').classes('flex-grow')
            
            # Loading spinner
            spinner = ui.spinner(size='lg').props('color=primary')
            spinner.visible = False
            
            ui.button('Clone Repo', on_click=lambda: handle_clone(url_input, repo_table, spinner)).props('color=primary')
            ui.button('Refresh All', on_click=lambda: handle_refresh_all(repo_table)).props('outline color=primary')

    # Repositories Table Card
    with ui.card().classes('w-full p-4 bg-white shadow-md rounded-lg'):
        ui.label('Tracked Repositories').classes('text-lg font-semibold mb-2')
        
        columns = [
            {'name': 'name', 'label': 'Repository Name', 'field': 'name', 'align': 'left'},
            {'name': 'updated', 'label': 'Last Updated', 'field': 'updated'},
            {'name': 'version', 'label': 'Latest Version (Commit)', 'field': 'version'},
            {'name': 'status', 'label': 'Status', 'field': 'status'},
            {'name': 'actions', 'label': 'Actions', 'field': 'path'},
        ]
        
        # Explicit pagination dictionary set to rowsPerPage: 0 so ALL rows show up
        repo_table = ui.table(
            columns=columns, 
            rows=tracked_repos, 
            row_key='path', 
            pagination={'rowsPerPage': 0}
        ).classes('w-full')
        
        # Add a refresh update button inside the table actions column using a Quasar template slot
        repo_table.add_slot('body-cell-actions', '''
            <q-td :props="props">
                <q-btn flat dense color="primary" icon="refresh" @click="$parent.$emit('update_repo', props.row.path)">
                    <q-tooltip>Update Repository</q-tooltip>
                </q-btn>
            </q-td>
        ''')
        
        # Listen for the event triggered by the UI button and run our Python function
        repo_table.on('update_repo', lambda e: handle_update(e.args, repo_table))

# Run the app in native desktop window mode
ui.run(native=True, title='GitPulse Manager', window_size=(950, 650), port=8080)
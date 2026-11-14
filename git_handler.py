import git
from pathlib import Path
from datetime import datetime

class GitManager:
    def __init__(self, base_dir="./cloned_repos"):
        # This creates a folder on your computer where all cloned repos will live
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

    def clone_repo(self, repo_url: str):
        """Clones a repository into the base directory."""
        # Extract the repository name from the URL (e.g., 'https://github.com/user/my-repo.git' -> 'my-repo')
        repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        target_path = self.base_dir / repo_name

        # Check if we already downloaded it
        if target_path.exists():
            return {"success": False, "message": f"Repository '{repo_name}' already exists locally."}

        try:
            # This is where GitPython actually runs 'git clone'
            git.Repo.clone_from(repo_url, target_path)
            return {"success": True, "message": f"Successfully cloned {repo_name}!", "path": str(target_path)}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def update_repo(self, repo_path: str):
        """Pulls the latest changes from the remote repository."""
        try:
            repo = git.Repo(repo_path)
            # Access the remote 'origin' and pull latest changes
            origin = repo.remotes.origin
            origin.pull()
            return {"success": True, "message": "Repository updated successfully."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_repo_metadata(self, repo_path: str):
        """Fetches latest commit info and update date for a local repo."""
        try:
            repo = git.Repo(repo_path)
            # Talk to GitHub/GitLab to fetch the latest changes
            repo.remotes.origin.fetch()
            
            latest_commit = repo.head.commit
            # Convert the raw timestamp into a readable date string (YYYY-MM-DD HH:MM)
            commit_date = datetime.fromtimestamp(latest_commit.committed_date).strftime('%Y-%m-%d %H:%M')
            # Grab the first 7 characters of the commit hash to act as our "version" identifier
            version_tag = latest_commit.hexsha[:7]  

            return {
                "name": Path(repo_path).name,
                "updated": commit_date,
                "version": version_tag,
                "status": "Up-to-date"
            }
        except Exception as e:
            return {"name": Path(repo_path).name, "updated": "Unknown", "version": "Error", "status": str(e)}

    
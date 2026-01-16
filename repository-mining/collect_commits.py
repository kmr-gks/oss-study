import argparse
import csv
import subprocess
import sys
import os
import re

def run_git_command(repo_path, command):
    """Runs a git command in the specified repository path."""
    try:
        result = subprocess.run(
            command,
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding='utf-8', 
            errors='replace', # Handle potential encoding issues
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        # Don't print error for remote get-url if it fails (e.g. no remote)
        if "remote" not in command:
             print(f"Error running git command: {e}")
             print(f"Stderr: {e.stderr}")
        return None

def get_repo_info(repo_path):
    """Extracts the repository owner and name from the origin URL."""
    url = run_git_command(repo_path, ["git", "remote", "get-url", "origin"])
    if not url:
        return "unknown", "unknown"
    
    # Handle SSH format: git@github.com:owner/repo.git
    match = re.search(r'[:/]([^/]+)/([^/]+)\.git$', url)
    if match:
        return match.group(1), match.group(2)
    
    # Handle HTTPS format: https://github.com/owner/repo.git
    parts = url.replace(".git", "").split("/")
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    
    return "unknown", "unknown"

def collect_commits(repo_path, output_file):
    print(f"Analyzing repository at {repo_path}...")
    
    # Verify it is a git repo
    if not os.path.exists(os.path.join(repo_path, ".git")):
         print(f"Error: {repo_path} is not a valid git repository.")
         sys.exit(1)

    repo_owner, repo_name = get_repo_info(repo_path)
    print(f"Repository: {repo_owner}/{repo_name}")

    # Git log command to get detailed info
    # Fields: Hash, Parent Hashes, Author Name, Author Email, Author Date, 
    #         Committer Name, Committer Email, Committer Date, Subject
    SEPARATOR = "|||---|||"
    # %H: commit hash
    # %P: parent hashes
    # %an: author name
    # %ae: author email
    # %at: author date, UNIX timestamp
    # %cn: committer name
    # %ce: committer email
    # %ct: committer date, UNIX timestamp
    # %s: subject
    log_format = f"%H{SEPARATOR}%P{SEPARATOR}%an{SEPARATOR}%ae{SEPARATOR}%at{SEPARATOR}%cn{SEPARATOR}%ce{SEPARATOR}%ct{SEPARATOR}%s"
    
    cmd_full = ["git", "log", f"--pretty=format:COMMIT:{log_format}", "--name-only"]
    full_output = run_git_command(repo_path, cmd_full)
    
    if not full_output:
        print("No commits found.")
        return

    with open(output_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        headers = [
            'Repository Owner',
            'Repository Name',
            'Commit Hash', 
            'Parent Hashes',
            'Author Name', 'Author Email', 'Author Date (UTC)',
            'Committer Name', 'Committer Email', 'Committer Date (UTC)',
            'Message', 
            'File Count'
        ]
        writer.writerow(headers)
        
        current_commit_data = None
        current_file_count = 0
        
        # Helper to convert timestamp to UTC string
        def format_date(timestamp_str):
            try:
                ts = int(timestamp_str)
                from datetime import datetime, timezone
                dt = datetime.fromtimestamp(ts, timezone.utc)
                return dt.isoformat()
            except ValueError:
                return timestamp_str

        # Helper to write the previous commit
        def write_commit(commit_data, file_count):
            if commit_data:
                # Parse and format dates (indices 4 and 7 in the split list)
                # 0: Hash, 1: Parents, 2: AuthName, 3: AuthEmail, 4: AuthDateTS
                # 5: CommitName, 6: CommitEmail, 7: CommitDateTS, 8: Msg
                if len(commit_data) >= 9:
                    commit_data[4] = format_date(commit_data[4])
                    commit_data[7] = format_date(commit_data[7])

                # Add Repo Owner and Name at the beginning and File Count at the end
                row = [repo_owner, repo_name] + commit_data + [file_count]
                writer.writerow(row)

        for line in full_output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            if line.startswith(f"COMMIT:"):
                # If we have a current commit, write it
                if current_commit_data:
                    write_commit(current_commit_data, current_file_count)
                
                # Start new commit
                raw_data = line[7:] # remove "COMMIT:"
                current_commit_data = raw_data.split(SEPARATOR)
                current_file_count = 0
            else:
                # This is a file line (or part of one)
                # git log --name-only ensures we get file paths
                current_file_count += 1
        
        # Write the last commit
        if current_commit_data:
             write_commit(current_commit_data, current_file_count)
                
    print(f"Finished! output saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect commit history from a git repository.")
    parser.add_argument("repo_path", help="Path to the git repository")
    parser.add_argument("--output", default="commits.csv", help="Output CSV file name")
    
    args = parser.parse_args()
    
    collect_commits(args.repo_path, args.output)

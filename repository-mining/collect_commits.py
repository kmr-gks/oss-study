import argparse
import csv
import subprocess
import sys
import os

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
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running git command: {e}")
        print(f"Stderr: {e.stderr}")
        return None

def collect_commits(repo_path, output_file):
    print(f"Analyzing repository at {repo_path}...")
    
    # Verify it is a git repo
    if not os.path.exists(os.path.join(repo_path, ".git")):
         print(f"Error: {repo_path} is not a valid git repository.")
         sys.exit(1)

    # Git log command to get hash, message, author, date
    # Format: Hash|Message|Author|Date
    # We use a custom separator that is unlikely to be in the commit message
    SEPARATOR = "|||---|||"
    log_format = f"%H{SEPARATOR}%s{SEPARATOR}%an{SEPARATOR}%ad"
    
    # First, get the commit details
    cmd_log = ["git", "log", f"--pretty=format:{log_format}"]
    log_output = run_git_command(repo_path, cmd_log)
    
    if not log_output:
        print("No commits found or error reading log.")
        return

    commits_data = []
    lines = log_output.strip().split('\n')
    
    print(f"Found {len(lines)} commits. Extracting file stats...")

    # For each commit, we want to find the modified files.
    # Running 'git show --name-only' for each commit can be slow for large repos.
    # Better approach: 'git log --name-status' returns files after the commit info.
    # Let's re-implement using a single command that includes file list.
    
    # Revised Git Command:
    # git log --pretty=format:"COMMIT:%H|%s|%an|%ad" --name-only
    # The output will be:
    # COMMIT:hash|msg|author|date
    # file1.txt
    # file2.py
    # empty line (between commits)
    
    cmd_full = ["git", "log", f"--pretty=format:COMMIT:{log_format}", "--name-only"]
    full_output = run_git_command(repo_path, cmd_full)
    
    if not full_output:
        return

    with open(output_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Hash', 'Message', 'Author', 'Date', 'Files Modified'])
        
        current_commit = None
        current_files = []
        
        # Helper to write the previous commit
        def write_commit(commit, files):
            if commit:
                parts = commit.split(SEPARATOR)
                if len(parts) >= 4:
                     h, m, a, d = parts[0], parts[1], parts[2], parts[3]
                     writer.writerow([h, m, a, d, "; ".join(files)])

        for line in full_output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            if line.startswith(f"COMMIT:"):
                # If we have a current commit, write it
                if current_commit:
                    write_commit(current_commit, current_files)
                
                # Start new commit
                current_commit = line[7:] # remove "COMMIT:"
                current_files = []
            else:
                # This is a file line
                current_files.append(line)
        
        # Write the last commit
        if current_commit:
             write_commit(current_commit, current_files)
                
    print(f"Finished! output saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect commit history from a git repository.")
    parser.add_argument("repo_path", help="Path to the git repository")
    parser.add_argument("--output", default="commits.csv", help="Output CSV file name")
    
    args = parser.parse_args()
    
    collect_commits(args.repo_path, args.output)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Git upload helper script"""

import os
import subprocess
import sys

# Change to script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

def run_cmd(cmd, check=True):
    """Run a command and print output"""
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if check and result.returncode != 0:
        print(f"Command failed with code {result.returncode}")
    return result.returncode == 0

def main():
    print("=" * 60)
    print("Night-Walk Git Upload")
    print("=" * 60)
    
    # Check if git is initialized
    if not os.path.exists('.git'):
        print("\n[1] Initializing git repository...")
        run_cmd(['git', 'init'])
    else:
        print("\n[1] Git repository already initialized")
    
    # Check remote
    print("\n[2] Checking remote...")
    result = subprocess.run(['git', 'remote', '-v'], capture_output=True, text=True)
    
    if not result.stdout.strip():
        print("No remote configured!")
        print("\nPlease create a GitHub repository and run:")
        print("  git remote add origin https://github.com/YOUR_USERNAME/Night-Walk.git")
        print("\nOr if using SSH:")
        print("  git remote add origin git@github.com:YOUR_USERNAME/Night-Walk.git")
        
        # Ask user for remote URL
        remote_url = input("\nEnter GitHub repository URL (or press Enter to skip): ").strip()
        if remote_url:
            run_cmd(['git', 'remote', 'add', 'origin', remote_url])
        else:
            print("Skipping remote setup. You can add it later.")
    else:
        print(result.stdout)
    
    # Add all files
    print("\n[3] Adding files...")
    run_cmd(['git', 'add', '.'])
    
    # Show status
    print("\n[4] Status:")
    run_cmd(['git', 'status'])
    
    # Commit
    print("\n[5] Committing...")
    commit_msg = "Add PWA support and ad entitlement system"
    run_cmd(['git', 'commit', '-m', commit_msg], check=False)
    
    # Check if remote exists before pushing
    result = subprocess.run(['git', 'remote', '-v'], capture_output=True, text=True)
    if 'origin' in result.stdout:
        print("\n[6] Pushing to GitHub...")
        # Try to push
        success = run_cmd(['git', 'push', '-u', 'origin', 'main'], check=False)
        if not success:
            print("\nTrying 'master' branch instead...")
            run_cmd(['git', 'push', '-u', 'origin', 'master'], check=False)
    else:
        print("\n[6] No remote configured. Skipping push.")
        print("Add remote with: git remote add origin <url>")
        print("Then push with: git push -u origin main")
    
    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == '__main__':
    main()

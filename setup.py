#!/usr/bin/env python3
"""Development environment setup script."""

import subprocess
import sys
import os


def run_command(cmd: str, cwd: str = ".") -> bool:
    """Run a shell command and return success status."""
    print(f"Running: {cmd} (in {cwd})")
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError:
        print(f"Command failed: {cmd}")
        return False


def setup_backend() -> bool:
    """Set up backend development environment."""
    print("Setting up backend...")

    if not os.path.exists("backend"):
        print("Backend directory not found")
        return False

    # Install backend dependencies
    if not run_command("python -m pip install -e .", "backend"):
        return False

    if not run_command("python -m pip install -r requirements-dev.txt", "backend"):
        return False

    return True


def setup_frontend() -> bool:
    """Set up frontend development environment."""
    print("Setting up frontend...")

    if not os.path.exists("frontend"):
        print("Frontend directory not found")
        return False

    # Install frontend dependencies
    if not run_command("npm install", "frontend"):
        return False

    return True





def main():
    """Main setup function."""
    print("Setting up Financial Planning development environment...")

    success = True

    success &= setup_backend()
    success &= setup_frontend()
    

    if success:
        print("\n✅ Development environment setup complete!")
        print("\nNext steps:")
        print("  Backend: make start-backend")
        print("  Frontend: make start-frontend")
    else:
        print("\n❌ Setup failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()

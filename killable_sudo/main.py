import os
import sys
import shutil
import subprocess

ROOT_SHIM_PATH = "/opt/killable-sudo/killable-sudo"
ROOT_SCRIPT_SOURCE = os.path.join(os.path.dirname(__file__), "root_script.py")

def install_root_shim():
    try:
        os.makedirs(os.path.dirname(ROOT_SHIM_PATH), exist_ok=True)
        shutil.copy2(ROOT_SCRIPT_SOURCE, ROOT_SHIM_PATH)
        os.chown(ROOT_SHIM_PATH, 0, 0)  # root:root
        os.chmod(ROOT_SHIM_PATH, 0o755)
        print(f"Installed root shim to {ROOT_SHIM_PATH}")
    except Exception as e:
        print(f"Failed to install root shim: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    # If --install passed, run installer and exit
    if "--install" in sys.argv:
        install_root_shim()
        sys.exit(0)

    # Check if root shim exists and is executable
    if not (os.path.isfile(ROOT_SHIM_PATH) and os.access(ROOT_SHIM_PATH, os.X_OK)):
        print(f"Root shim not found or not executable at {ROOT_SHIM_PATH}.", file=sys.stderr)
        print("Run with --install to install the root shim.", file=sys.stderr)
        print("Make sure your sudoers allows users to run this file with sudo without password by adding this entry with visudo")
        print(f"yourusername ALL=(ALL) NOPASSWD: {ROOT_SHIM_PATH}")
        sys.exit(1)

    # Exec the root shim with all passed arguments (except --install)
    args = [ROOT_SHIM_PATH] + sys.argv[1:]
    print('Running')
    os.execv(ROOT_SHIM_PATH, args)

if __name__ == "__main__":
    main()

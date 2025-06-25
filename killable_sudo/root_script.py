#!/usr/bin/python3
import argparse
import os
import sys
import json
import pwd
import logging
import subprocess
import signal
from pathlib import Path
import secrets
import threading
import select
import shlex

if os.environ.get("DEBUG"):
    logging.basicConfig(level=logging.DEBUG)


BASE_RUN_DIR = Path("/var/run/killable-sudo")

def ensure_dir(path: Path, mode=0o750, owner_uid=0, owner_gid=0):
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, mode)
    os.chown(path, owner_uid, owner_gid)

def init_fifodir(username: str):
    logging.debug(f"Initializing FIFO directory for user {username}")
    try:
        user_info = pwd.getpwnam(username)
    except KeyError:
        logging.error(f"User {username} not found")
        return 1

    user_dir = BASE_RUN_DIR / f"user-{username}"
    ensure_dir(BASE_RUN_DIR, mode=0o755, owner_uid=0, owner_gid=0)
    ensure_dir(user_dir, mode=0o770, owner_uid=0, owner_gid=user_info.pw_gid)
    # Set ownership to root:usergroup, so root owns but group is user's primary group
    os.chown(user_dir, 0, user_info.pw_gid)

    return 0

def kill_pid_from_fifo(fifo_path: Path):
    """Read kill command from fifo and kill the target pid."""
    try:
        pid_str = fifo_path.name.split("pid-")[-1].split(".fifo")[0]
        pid = int(pid_str)
    except Exception as e:
        logging.error(f"Invalid fifo filename {fifo_path}: {e}")
        return 1

    logging.debug(f"Sending SIGTERM to PID {pid} for fifo {fifo_path}")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        logging.warning(f"PID {pid} does not exist")
        return 1
    return 0

def run_root_shim(args):
    """
    Root shim main entrypoint.
    Dispatches actions based on command-line arguments.
    """

    if args.init_fifodir:
        username = args.init_fifodir
        ret = init_fifodir(username)
        sys.exit(ret)

    elif args.command:
        if not args.fifo_path:
            raise Exception("Missing --fifo-path for --command")
        cmd_list = shlex.split(args.command)
        run_command_and_watch_fifo(args.fifo_path, cmd_list)

    elif args.kill:
        if not args.fifo_path:
            raise Exception("Missing --fifo-path for --kill")
        ret = kill_pid_from_fifo(args.fifo_path)
        sys.exit(ret)

    else:
        raise Exception("No valid action provided to root shim.")


def user_init_fifo_dir():
    username = pwd.getpwuid(os.getuid()).pw_name

    cmd = [
        "sudo",
        "/opt/killable-sudo/killable-sudo",
        "--root-shim",
        "--init-fifodir", username
    ]

    subprocess.check_call(cmd)

def run_user_shim(args):
    """
    User shim:
    - Creates the FIFO
    - Launches the target command as a subprocess
    - Waits for signals to trigger kills via root shim
    """

    username = pwd.getpwuid(os.getuid()).pw_name
    user_dir = BASE_RUN_DIR / f"user-{username}"

    nonce = secrets.token_hex(8)  # 16-character secure random hex string
    fifo_path = user_dir / f"pid-{os.getpid()}-{nonce}.fifo"

    if fifo_path.exists():
        fifo_path.unlink()
    os.mkfifo(fifo_path, mode=0o600)

    user_init_fifo_dir()

    # Now run the actual command passed as args
    if not args:
        raise Exception("No command specified to run under user shim")

    def forward_kill(fifo_path: Path):
        with open(fifo_path, 'wb', buffering=0) as stream:
            stream.write(b"kill\n")
            stream.flush()
            stream.close()


    # Signal handler for SIGINT, SIGTERM to forward kill to root shim
    def sig_handler(signum, frame):
        forward_kill(fifo_path)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    ret = run_user_command(args, fifo_path)

    # Clean up fifo
    try:
        fifo_path.unlink()
    except Exception:
        pass

    return ret


def run_user_command(args, fifo_path):
    cmd = [
        "sudo",
        "/opt/killable-sudo/killable-sudo",
        "--root-shim",
        "--fifo-path", str(fifo_path),
        "--command", " ".join(shlex.quote(arg) for arg in args)
    ]

    result = subprocess.run(cmd)
    return result.returncode


def run_command_and_watch_fifo(fifo_path: Path, cmd: list):
    """
    Run command asynchronously and watch fifo_path for 'kill\n'.
    If 'kill\n' is received, terminate the command.
    When the command exits, return its exit code.
    """
    # Open the fifo for reading in non-blocking mode
    fd = os.open(str(fifo_path), os.O_RDONLY | os.O_NONBLOCK)

    # Start the subprocess
    print('running subprocess')
    proc = subprocess.Popen(["sudo", "-u", proc_owner(fifo_path), "sudo"] + cmd)

    # Create a pipe for signaling subprocess exit
    rpipe, wpipe = os.pipe()

    def wait_proc():
        proc.wait()
        os.close(wpipe)  # Closing write end signals EOF to main thread

    threading.Thread(target=wait_proc, daemon=True).start()

    try:
        while True:
            rlist, _, _ = select.select([fd, rpipe], [], [])

            if rpipe in rlist:
                data = os.read(rpipe, 1024)
                if len(data) == 0:
                    # EOF on pipe, subprocess exited
                    break

            if fd in rlist:
                try:
                    data = os.read(fd, 1024)
                except BlockingIOError:
                    continue

                if data == b"":
                    # FIFO closed by writer, nothing more to read
                    continue

                # Check if kill command received
                if b"kill\n" in data:
                    logging.info("Kill command received on fifo, terminating subprocess")
                    proc.terminate()

        retcode = proc.poll()
        if retcode is None:
            # Subprocess still running, wait for it
            retcode = proc.wait()

    finally:
        os.close(fd)
        os.close(rpipe)
        # wpipe already closed by thread

    sys.exit(retcode)

def proc_owner(fifo_path: Path) -> str:
    # Helper to get username from fifo ownership
    st = fifo_path.stat()
    import pwd
    return pwd.getpwuid(st.st_uid).pw_name

def main():
    if os.geteuid() == 0:
        # Running as root -> root shim
        args = parse_root_arguments()
        run_root_shim(args)
    else:
        # Running as user -> user shim
        args = sys.argv[1:]
        if not args:
            print("Usage: killable-sudo [command args...]")
            sys.exit(1)
        sys.exit(run_user_shim(args))


def parse_root_arguments():
    root_parser = argparse.ArgumentParser(
        description="Killable Sudo Root Shim (INTERNAL USE)",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=True # Allow help for root shim actions if called directly for debugging
    )

    root_parser.add_argument("--root-shim", action="store_true", help=argparse.SUPPRESS)
    root_parser.add_argument(
        "--fifo-path",
        type=Path,
        help="Path to the FIFO to monitor for signals."
    )

    root_action_group = root_parser.add_mutually_exclusive_group(required=True)

    root_action_group.add_argument(
        "--init-fifodir", 
        metavar="USERNAME", 
        help="Initialize FIFO directory for a given username."
    )

    root_action_group.add_argument(
        "--command",
        help="Command to execute (e.g., --command 'sleep 60')."
    )

    root_action_group.add_argument(
        "--kill", 
        action='store_true',
        default=False,
    )
    return root_parser.parse_args()
        

if __name__ == "__main__":
    main()

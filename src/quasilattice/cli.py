from . import __version__
import os
import sys
import platform
import argparse
import shutil
import subprocess
import pathlib
import getpass

SERVICE_NAME = "quasilattice"

def run(args):
    """
    Run the QuasiLattice in the foreground.
    """
    import uvicorn
    if sys.stdout is None or sys.stderr is None:
        log_dir = pathlib.Path.home() / ".quasilattice" # TODO: load from config
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = open(log_dir / "quasilattice.log", "a", buffering=1)
        sys.stdout = log_file
        sys.stderr = log_file
    if not args.host:
        args.host = "127.0.0.1"  # TODO: load host from config
    if not args.port:
        args.port = 8312  # TODO: load port from config
    uvicorn.run("quasilattice.api:app", host=args.host, port=args.port)

def setup(args):
    """
    Setup the QuasiLattice background service.
    """
    system = platform.system()
    if args.verbose:
        print("QuasiLattice Version:",__version__)
        print("Operating System:",system)
    if system == "Linux":
        # TODO: Add support for other init systems?
        if args.system and os.geteuid() != 0:
            print("System service installation requires root privileges.")
            print("Please run:")
            print("  sudo quasilattice setup --system")
            return
        if (shutil.which("systemctl") is not None):
            setup_systemd_service(args.system,args.verbose)
        else:
            raise RuntimeError("systemd is not installed.")
    elif system == "Windows":
        setup_windows_service(args.system,args.verbose)
    elif system == "Darwin":
        setup_launchd_service(args.system,args.verbose)
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

def remove(args):
    """
    Remove the QuasiLattice background service.
    """
    system = platform.system()
    if args.verbose:
        print("QuasiLattice Version:",__version__)
        print("Operating System:",system)
    if system == "Linux":
        # TODO: Add support for other init systems?
        if args.system and os.geteuid() != 0:
            print("System service removal requires root privileges.")
            print("Please run:")
            print("  sudo quasilattice remove --system")
            return
        if (shutil.which("systemctl") is not None):
            remove_systemd_service(args.system,args.verbose)
        else:
            raise RuntimeError("systemd is not installed.")
    elif system == "Windows":
        remove_windows_service(args.system,args.verbose)
    elif system == "Darwin":
        remove_launchd_service(args.system,args.verbose)
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

def start(args):
    system = platform.system()
    if args.verbose:
        print("QuasiLattice Version:",__version__)
        print("Operating System:",system)
    if system == "Linux":
        # TODO: Add support for other init systems?
        if (shutil.which("systemctl") is not None):
            start_systemd_service(args.system,args.verbose)
        else:
            raise RuntimeError("systemd is not installed.")
    elif system == "Windows":
        start_windows_service(args.system,args.verbose)
    elif system == "Darwin":
        start_launchd_service(args.system,args.verbose)
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

def stop(args):
    system = platform.system()
    if args.verbose:
        print("QuasiLattice Version:",__version__)
        print("Operating System:",system)
    if system == "Linux":
        # TODO: Add support for other init systems?
        if (shutil.which("systemctl") is not None):
            stop_systemd_service(args.system,args.verbose)
        else:
            raise RuntimeError("systemd is not installed.")
    elif system == "Windows":
        stop_windows_service(args.system,args.verbose)
    elif system == "Darwin":
        stop_launchd_service(args.system,args.verbose)
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

def status(args):
    system = platform.system()
    if args.verbose:
        print("QuasiLattice Version:",__version__)
        print("Operating System:",system)
    if system == "Linux":
        # TODO: Add support for other init systems?
        if (shutil.which("systemctl") is not None):
            status_systemd_service(args.system,args.verbose)
        else:
            raise RuntimeError("systemd is not installed.")
    elif system == "Windows":
        status_windows_service(args.system,args.verbose)
    elif system == "Darwin":
        status_launchd_service(args.system,args.verbose)
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

def setup_systemd_service(system: bool = False, verbose: bool = False):
    if system:
        user_line: str = ""
        service_path = pathlib.Path(f"/etc/systemd/system/{SERVICE_NAME}.service")
        systemctl = ["systemctl"]
    else:
        user_line: str = "User="+getpass.getuser()+"\n"
        service_path = pathlib.Path(f"{pathlib.Path.home()}/.config/systemd/user/{SERVICE_NAME}.service")
        systemctl = ["systemctl", "--user"]
    if verbose:
        print("Installing service at:",service_path)
    service_path.parent.mkdir(parents=True, exist_ok=True)
    service_path.write_text(f"""
[Unit]
Description=QuasiLattice Background Service
After=network.target

[Service]
Type=simple
{user_line}ExecStart={sys.executable} -m quasilattice run
Restart=always
RestartSec=5

[Install]
WantedBy={"multi-user.target" if system else "default.target"}
""")
    stdout = None if verbose else subprocess.DEVNULL
    subprocess.run([*systemctl, "daemon-reload"], check=True, stdout=stdout, stderr = stdout)
    subprocess.run([*systemctl, "enable", SERVICE_NAME], check=True, stdout=stdout, stderr = stdout)
    subprocess.run([*systemctl, "start", SERVICE_NAME], check=True, stdout=stdout, stderr = stdout)
    if verbose:
        print("QuasiLattice service setup successfully!")

def remove_systemd_service(system: bool = False, verbose: bool = False):
    system_service_path = pathlib.Path(f"/etc/systemd/system/{SERVICE_NAME}.service")
    user_service_path = pathlib.Path(f"{pathlib.Path.home()}/.config/systemd/user/{SERVICE_NAME}.service")
    if system:
        service_path = system_service_path
        systemctl = ["systemctl"]
    else:
        service_path = user_service_path
        systemctl = ["systemctl", "--user"]
    if not service_path.exists():
        print("No service found at",service_path)
        if system_service_path.exists():
            print("But a service was discovered at",system_service_path)
            print("To remove it, run:")
            print("  quasilattice remove --system")
        elif user_service_path.exists():
            print("But a service was discovered at",user_service_path)
            print("To remove it, run:")
            print("  quasilattice remove")
        else:
            print("Nothing to remove.")
        return
    if verbose:
        print("Removing service from:",service_path)
    stdout = None if verbose else subprocess.DEVNULL
    subprocess.run([*systemctl, "stop", SERVICE_NAME], check=True, stdout = stdout, stderr = stdout)
    subprocess.run([*systemctl, "disable", SERVICE_NAME], check=True, stdout = stdout, stderr = stdout)
    service_path.unlink()
    subprocess.run([*systemctl, "daemon-reload"], check=True, stdout = stdout, stderr = stdout)
    if verbose:
        print("QuasiLattice service removed.")

def start_systemd_service(system: bool = False, verbose: bool = False):
    systemctl = ["systemctl"] if system else ["systemctl", "--user"]
    systemctl_inverted = ["systemctl", "--user"] if system else ["systemctl"]
    result = subprocess.run([*systemctl, "cat", SERVICE_NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    if result.returncode != 0:
        result = subprocess.run([*systemctl_inverted, "cat", SERVICE_NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
        if result.returncode != 0:
            print("QuasiLattice service is not setup.")
            print("You can install it by running:")
            print("  quasilattice setup")
            return
        else:
            try:
                subprocess.run([*systemctl_inverted, "start", SERVICE_NAME], check=True)
            except Exception as e:
                print("Failed to start QuasiLattice service.")
                if verbose:
                    raise e
    else:
        try:
            subprocess.run([*systemctl, "start", SERVICE_NAME], check=True)
        except Exception as e:
            print("Failed to start QuasiLattice service.")
            if verbose:
                raise e
            return
    if verbose:
        print("QuasiLattice service started.")

def stop_systemd_service(system: bool = False, verbose: bool = False):
    systemctl = ["systemctl"] if system else ["systemctl", "--user"]
    systemctl_inverted = ["systemctl", "--user"] if system else ["systemctl"]
    result = subprocess.run([*systemctl, "cat", SERVICE_NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    if result.returncode != 0:
        result = subprocess.run([*systemctl_inverted, "cat", SERVICE_NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
        if result.returncode != 0:
            print("QuasiLattice service is not setup.")
            print("You can install it by running:")
            print("  quasilattice setup")
            return
        else:
            try:
                subprocess.run([*systemctl_inverted, "stop", SERVICE_NAME], check=True)
            except Exception as e:
                print("Failed to stop QuasiLattice service.")
                if verbose:
                    raise e
    else:
        try:
            subprocess.run([*systemctl, "stop", SERVICE_NAME], check=True)
        except Exception as e:
            print("Failed to stop QuasiLattice service.")
            if verbose:
                raise e
            return
    if verbose:
        print("QuasiLattice service stopped.")

def status_systemd_service(system: bool = False, verbose: bool = False):
    systemctl = ["systemctl"] if system else ["systemctl", "--user"]
    systemctl_inverted = ["systemctl", "--user"] if system else ["systemctl"]
    result = subprocess.run([*systemctl, "cat", SERVICE_NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    if result.returncode != 0:
        result = subprocess.run([*systemctl_inverted, "cat", SERVICE_NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
        if result.returncode != 0:
            print("QuasiLattice service is not setup.")
            print("You can install it by running:")
            print("  quasilattice setup")
            return
        else:
            try:
                subprocess.run([*systemctl_inverted, "--no-pager", "-l", "status", SERVICE_NAME], check=False)
            except Exception as e:
                print("Failed to check status of QuasiLattice service.")
                if verbose:
                    raise e
    else:
        try:
            subprocess.run([*systemctl, "--no-pager", "-l", "status", SERVICE_NAME], check=False)
        except Exception as e:
            print("Failed to check status of QuasiLattice service.")
            if verbose:
                raise e

def setup_launchd_service(system: bool = False, verbose: bool = False):
    if system: # TODO: add support for system-wide (daemon) service setup.
        print("System-wide (daemon) service setup is not supported on macOS.")
        print("Please run without --system.")
        return
    plist_content = f"""
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{SERVICE_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>-m</string>
        <string>quasilattice</string>
        <string>run</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
"""
    plist_path = pathlib.Path.home() / "Library/LaunchAgents" / f"{SERVICE_NAME}.plist"
    plist_path.write_text(plist_content)
    stdout = None if verbose else subprocess.DEVNULL
    subprocess.run(["launchctl", "load", str(plist_path)], check=True, stdout = stdout, stderr = stdout)
    if verbose:
        print("QuasiLattice service setup successfully!")

def remove_launchd_service(system: bool = False, verbose: bool = False):
    if system: # TODO: add support for system-wide (daemon) service removal.
        print("System-wide (daemon) service removal is not supported on macOS.")
        print("Please run without --system.")
        return
    plist_path = pathlib.Path.home() / "Library/LaunchAgents" / f"{SERVICE_NAME}.plist"
    if not plist_path.exists():
        print("No service found at",plist_path)
        print("Nothing to remove.")
        return
    if verbose:
        print("Removing service from:",plist_path)
    stdout = None if verbose else subprocess.DEVNULL
    subprocess.run(["launchctl", "unload", str(plist_path)], check=True, stdout = stdout, stderr = stdout)
    plist_path.unlink()
    if verbose:
        print("QuasiLattice service removed.")

def start_launchd_service(system: bool = False, verbose: bool = False):
    if system: # TODO: add support for system-wide (daemon) service management.
        print("System-wide (daemon) service management is not supported on macOS.")
        print("Please run without --system.")
        return
    plist_path = pathlib.Path.home() / "Library/LaunchAgents" / f"{SERVICE_NAME}.plist"
    stdout = None if verbose else subprocess.DEVNULL
    try:
        subprocess.run(["launchctl", "load", str(plist_path)], check=True, stdout = stdout, stderr = stdout)
    except Exception as e:
        print("QuasiLattice service is not setup.")
        print("You can install it by running:")
        print("  quasilattice setup")
        if verbose:
            raise e
        return
    if verbose:
        print("QuasiLattice service started.")

def stop_launchd_service(system: bool = False, verbose: bool = False):
    if system: # TODO: add support for system-wide (daemon) service management.
        print("System-wide (daemon) service management is not supported on macOS.")
        print("Please run without --system.")
        return
    plist_path = pathlib.Path.home() / "Library/LaunchAgents" / f"{SERVICE_NAME}.plist"
    stdout = None if verbose else subprocess.DEVNULL
    try:
        subprocess.run(["launchctl", "unload", str(plist_path)], check=True, stdout = stdout, stderr = stdout)
    except Exception as e:
        print("QuasiLattice service is not setup.")
        print("You can install it by running:")
        print("  quasilattice setup")
        if verbose:
            raise e
        return
    if verbose:
        print("QuasiLattice service stopped.")

def status_launchd_service(system: bool = False, verbose: bool = False):
    if system: # TODO: add support for system-wide (daemon) service management.
        print("System-wide (daemon) service management is not supported on macOS.")
        print("Please run without --system.")
        return
    try:
        subprocess.run(["launchctl", "list", SERVICE_NAME])
    except Exception as e:
        print("QuasiLattice service is not setup.")
        print("You can install it by running:")
        print("  quasilattice setup")
        if verbose:
            raise e

def get_windows_executable() -> str:
    """
    Return the path to pythonw.exe if available, so the scheduled task
    runs without popping up a console window. Falls back to sys.executable
    if pythonw.exe can't be found.
    """
    exe_path = pathlib.Path(sys.executable)
    pythonw_path = exe_path.parent / "pythonw.exe"
    if pythonw_path.exists():
        return str(pythonw_path)
    return sys.executable

def setup_windows_service(system: bool = False, verbose: bool = False):
    if system:
        print("Note: --system is not used on Windows; the scheduled task runs at user logon regardless.")
    windows_exe = get_windows_executable()
    if verbose:
        print("Using exe:",windows_exe)
    result = subprocess.run(
        ["schtasks", "/Create", "/SC", "ONLOGON", "/RL", "HIGHEST", "/TN", SERVICE_NAME,
         "/TR", f'"{windows_exe}" -m quasilattice run', "/F"],
        capture_output=True, text=True, check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        print("Failed to setup the QuasiLattice service:")
        print((result.stderr or result.stdout).strip())
        return
    if verbose:
        print("QuasiLattice service setup successfully!")


def remove_windows_service(system: bool = False, verbose: bool = False):
    if system:
        print("Note: --system is not used on Windows.")
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", SERVICE_NAME, "/F"],
        capture_output=True, text=True, check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        if ("The system cannot find the file specified." in (result.stderr or result.stdout).strip()):
            if verbose:
                print("Failed to remove the QuasiLattice service:")
                print((result.stderr or result.stdout).strip())
            print("QuasiLattice service is not setup.")
            print("Nothing to remove.")
        else:
            print("Failed to remove the QuasiLattice service:")
            print((result.stderr or result.stdout).strip())
        return
    if verbose:
        print("QuasiLattice service removed.")

def start_windows_service(system: bool = False, verbose: bool = False):
    if system:
        print("Note: --system is not used on Windows.")
    result = subprocess.run(
        ["schtasks", "/Run", "/TN", SERVICE_NAME],
        capture_output=True, text=True, check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        if ("The system cannot find the file specified." in (result.stderr or result.stdout).strip()):
            if verbose:
                print("Failed to start the QuasiLattice service:")
                print((result.stderr or result.stdout).strip())
            print("QuasiLattice service is not setup.")
            print("You can install it by running:")
            print("  quasilattice setup")
        else:
            print("Failed to start the QuasiLattice service:")
            print((result.stderr or result.stdout).strip())
    if verbose:
        print("QuasiLattice service started.")

def stop_windows_service(system: bool = False, verbose: bool = False):
    if system:
        print("Note: --system is not used on Windows.")
    result = subprocess.run(
        ["schtasks", "/End", "/TN", SERVICE_NAME],
        capture_output=True, text=True, check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        if ("The system cannot find the file specified." in (result.stderr or result.stdout).strip()):
            if verbose:
                print("Failed to stop the QuasiLattice service:")
                print((result.stderr or result.stdout).strip())
            print("QuasiLattice service is not setup.")
            print("You can install it by running:")
            print("  quasilattice setup")
        else:
            print("Failed to stop the QuasiLattice service:")
            print((result.stderr or result.stdout).strip())
        return
    if verbose:
        print("QuasiLattice service stopped.")

def status_windows_service(system: bool = False, verbose: bool = False):
    if system:
        print("Note: --system is not used on Windows.")
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", SERVICE_NAME],
        capture_output=True, text=True, check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        if ("The system cannot find the file specified." in (result.stderr or result.stdout).strip()):
            if verbose:
                print((result.stderr or result.stdout).strip())
            print("QuasiLattice service is not setup.")
            print("You can install it by running:")
            print("  quasilattice setup")
        else:
            print((result.stderr or result.stdout).strip())
        return
    print(result.stdout.strip())

def main():
    """Configure and run QuasiLattice from the terminal."""
    parser = argparse.ArgumentParser(
        description="A data analysis, knowledge base, journaling and note taking system."
    )
    parser.set_defaults(func=status)
    parser.add_argument("-v", "--verbose", action="store_true", help="Provide additional output.")
    parser.add_argument("--system", action="store_true", help="System service. Requires elevated permissions.")
    
    subparsers = parser.add_subparsers(
        dest="command", 
        required=False
    )
    run_subparser: argparse.ArgumentParser = subparsers.add_parser("run", help="Run QuasiLattice in the foreground.")
    run_subparser.set_defaults(func=run)
    run_subparser.add_argument("-v", "--verbose", action="store_true", help="Provide additional output.")
    run_subparser.add_argument("--host",help="Host address to bind to.")
    run_subparser.add_argument("--port",help="Port to bind to.")

    service_commands = {"setup":setup,"remove":remove,"start":start,"stop":stop,"status":status}
    for service_command, command_func in service_commands.items():
        subparser: argparse.ArgumentParser = subparsers.add_parser(service_command, help=service_command.capitalize()+" the QuasiLattice background service.")
        subparser.set_defaults(func=command_func)
        subparser.add_argument("-v", "--verbose", action="store_true", help="Provide additional output.")
        subparser.add_argument("--system", action="store_true", help="System service. Requires elevated permissions.")

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
import quasilattice
import os
import sys
import platform
import argparse
import shutil
import subprocess
import getpass
import logging

SERVICE_NAME = "quasilattice"

logger = logging.getLogger("quasilattice")

def run(args):
    """
    Run the QuasiLattice in the foreground.
    """
    if args.debug:
        quasilattice.run(config_path = args.config_path, log_level = 5)
    else:
        quasilattice.run(config_path = args.config_path, log_level = args.log_level)

def setup(args):
    """
    Setup the QuasiLattice background service.
    """
    quasilattice.init(
        config_path=args.config_path,
        log_level=5 if args.debug else args.log_level,
    )
    system = platform.system()
    logger.debug(f"QuasiLattice Version: {quasilattice.__version__}")
    logger.debug(f"Operating System: {system}")
    if system == "Linux":
        if args.system and os.geteuid() != 0:
            logger.error("System service installation requires root privileges.")
            logger.info("Please run: sudo quasilattice setup --system")
            return
        if (shutil.which("systemctl") is not None):
            setup_systemd_service(args.system)
        else:
            logger.error("systemd is not installed.")
            logger.info("Quasilattice can still be run manually with: quasilattice run")
    elif system == "Windows":
        setup_windows_service(args.system)
    elif system == "Darwin":
        setup_launchd_service(args.system)
    else:
        logger.error(f"Unsupported OS: {system}")
        logger.info("Quasilattice can still be run manually with: quasilattice run")

def remove(args):
    """
    Remove the QuasiLattice background service.
    """
    quasilattice.init(
         config_path=args.config_path,
        log_level=5 if args.debug else args.log_level,
    )
    system = platform.system()
    logger.debug(f"QuasiLattice Version: {quasilattice.__version__}")
    logger.debug(f"Operating System: {system}")
    if system == "Linux":
        if args.system and os.geteuid() != 0:
            logger.error("System service removal requires root privileges.")
            logger.info("Please run: sudo quasilattice remove --system")
            return
        if (shutil.which("systemctl") is not None):
            remove_systemd_service(args.system)
        else:
            logger.error("systemd is not installed.")
            logger.info("Quasilattice can still be run manually with: quasilattice run")
    elif system == "Windows":
        remove_windows_service(args.system)
    elif system == "Darwin":
        remove_launchd_service(args.system)
    else:
        logger.error(f"Unsupported OS: {system}")
        logger.info("Quasilattice can still be run manually with: quasilattice run")

def start(args):
    quasilattice.init(
         config_path=args.config_path,
        log_level=5 if args.debug else args.log_level,
    )
    system = platform.system()
    logger.debug(f"QuasiLattice Version: {quasilattice.__version__}")
    logger.debug(f"Operating System: {system}")
    if system == "Linux":
        if (shutil.which("systemctl") is not None):
            start_systemd_service(args.system)
        else:
            logger.error("systemd is not installed.")
            logger.info("Quasilattice can still be run manually with: quasilattice run")
    elif system == "Windows":
        start_windows_service(args.system)
    elif system == "Darwin":
        start_launchd_service(args.system)
    else:
        logger.error(f"Unsupported OS: {system}")
        logger.info("Quasilattice can still be run manually with: quasilattice run")

def stop(args):
    quasilattice.init(
         config_path=args.config_path,
        log_level=5 if args.debug else args.log_level,
    )
    system = platform.system()
    logger.debug(f"QuasiLattice Version: {quasilattice.__version__}")
    logger.debug(f"Operating System: {system}")
    if system == "Linux":
        if (shutil.which("systemctl") is not None):
            stop_systemd_service(args.system)
        else:
            logger.error("systemd is not installed.")
            logger.info("Quasilattice can still be run manually with: quasilattice run")
    elif system == "Windows":
        stop_windows_service(args.system)
    elif system == "Darwin":
        stop_launchd_service(args.system)
    else:
        logger.error(f"Unsupported OS: {system}")
        logger.info("Quasilattice can still be run manually with: quasilattice run")

def status(args):
    quasilattice.init(
         config_path=args.config_path,
        log_level=5 if args.debug else args.log_level,
    )
    system = platform.system()
    logger.debug(f"QuasiLattice Version: {quasilattice.__version__}")
    logger.debug(f"Operating System: {system}")
    if system == "Linux":
        if (shutil.which("systemctl") is not None):
            status_systemd_service(args.system)
        else:
            logger.error("systemd is not installed.")
            logger.info("Quasilattice can still be run manually with: quasilattice run")
    elif system == "Windows":
        status_windows_service(args.system)
    elif system == "Darwin":
        status_launchd_service(args.system)
    else:
        logger.error(f"Unsupported OS: {system}")
        logger.info("Quasilattice can still be run manually with: quasilattice run")

def setup_systemd_service(system: bool = False):
    if system:
        user_line: str = ""
        service_path = os.path.join("/etc","systemd","system",f"{SERVICE_NAME}.service")
        systemctl = ["systemctl"]
    else:
        user_line: str = "User="+getpass.getuser()+"\n"
        service_path = os.path.join(os.path.expanduser("~"),".config","systemd","user",f"{SERVICE_NAME}.service")
        systemctl = ["systemctl", "--user"]
    logger.debug(f"Installing service at: {service_path}")
    os.makedirs(os.path.dirname(service_path), exist_ok=True)
    with open(service_path, "w") as service_file: 
        service_file.write(f"""
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
    stdout = None if logger.getEffectiveLevel() <= 10 else subprocess.DEVNULL
    subprocess.run([*systemctl, "daemon-reload"], check=True, stdout=stdout, stderr = stdout)
    subprocess.run([*systemctl, "enable", SERVICE_NAME], check=True, stdout=stdout, stderr = stdout)
    subprocess.run([*systemctl, "start", SERVICE_NAME], check=True, stdout=stdout, stderr = stdout)
    if logger.getEffectiveLevel() <= 10:
        logger.info("QuasiLattice systemd service setup successfully!")

def remove_systemd_service(system: bool = False):
    system_service_path = os.path.join("/etc","systemd","system",f"{SERVICE_NAME}.service")
    user_service_path = os.path.join(os.path.expanduser("~"),".config","systemd","user",f"{SERVICE_NAME}.service")
    if system:
        service_path = system_service_path
        systemctl = ["systemctl"]
    else:
        service_path = user_service_path
        systemctl = ["systemctl", "--user"]
    if not os.path.isfile(service_path):
        logger.error(f"No service found at {service_path}")
        if os.path.isfile(system_service_path):
            logger.info(f"But a service was discovered at {system_service_path}")
            logger.info("To remove it, run: quasilattice remove --system")
        elif os.path.isfile(user_service_path):
            logger.info(f"But a service was discovered at {user_service_path}")
            logger.info("To remove it, run: quasilattice remove")
        else:
            logger.info("Nothing to remove.")
        return
    logger.debug(f"Removing service from: {service_path}")
    stdout = None if logger.getEffectiveLevel() <= 10 else subprocess.DEVNULL
    subprocess.run([*systemctl, "stop", SERVICE_NAME], check=True, stdout = stdout, stderr = stdout)
    subprocess.run([*systemctl, "disable", SERVICE_NAME], check=True, stdout = stdout, stderr = stdout)
    os.unlink(service_path)
    subprocess.run([*systemctl, "daemon-reload"], check=True, stdout = stdout, stderr = stdout)
    logger.debug("QuasiLattice service removed.")

def start_systemd_service(system: bool = False):
    systemctl = ["systemctl"] if system else ["systemctl", "--user"]
    systemctl_inverted = ["systemctl", "--user"] if system else ["systemctl"]
    result = subprocess.run([*systemctl, "cat", SERVICE_NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    if result.returncode != 0:
        result = subprocess.run([*systemctl_inverted, "cat", SERVICE_NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
        if result.returncode != 0:
            logger.error("QuasiLattice service is not setup.")
            logger.info("You can install it by running: quasilattice setup")
            return
        else:
            try:
                subprocess.run([*systemctl_inverted, "start", SERVICE_NAME], check=True)
            except Exception as e:
                logger.error("Failed to start QuasiLattice service.")
                if logger.getEffectiveLevel() <= 10:
                    raise e
                return
    else:
        try:
            subprocess.run([*systemctl, "start", SERVICE_NAME], check=True)
        except Exception as e:
            logger.error("Failed to start QuasiLattice service.")
            if logger.getEffectiveLevel() <= 10:
                raise e
            return
    logger.debug("QuasiLattice service started.")

def stop_systemd_service(system: bool = False):
    systemctl = ["systemctl"] if system else ["systemctl", "--user"]
    systemctl_inverted = ["systemctl", "--user"] if system else ["systemctl"]
    result = subprocess.run([*systemctl, "cat", SERVICE_NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    if result.returncode != 0:
        result = subprocess.run([*systemctl_inverted, "cat", SERVICE_NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
        if result.returncode != 0:
            logger.error("QuasiLattice service is not setup.")
            logger.info("You can install it by running: quasilattice setup")
            return
        else:
            try:
                subprocess.run([*systemctl_inverted, "stop", SERVICE_NAME], check=True)
            except Exception as e:
                logger.error("Failed to stop QuasiLattice service.")
                if logger.getEffectiveLevel() <= 10:
                    raise e
                return
    else:
        try:
            subprocess.run([*systemctl, "stop", SERVICE_NAME], check=True)
        except Exception as e:
            logger.error("Failed to stop QuasiLattice service.")
            if logger.getEffectiveLevel() <= 10:
                raise e
            return
    logger.debug("QuasiLattice service stopped.")

def status_systemd_service(system: bool = False):
    systemctl = ["systemctl"] if system else ["systemctl", "--user"]
    systemctl_inverted = ["systemctl", "--user"] if system else ["systemctl"]
    result = subprocess.run([*systemctl, "cat", SERVICE_NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    if result.returncode != 0:
        result = subprocess.run([*systemctl_inverted, "cat", SERVICE_NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
        if result.returncode != 0:
            logger.error("QuasiLattice service is not setup.")
            logger.info("You can install it by running: quasilattice setup")
            return
        else:
            try:
                subprocess.run([*systemctl_inverted, "--no-pager", "-l", "status", SERVICE_NAME], check=False)
            except Exception as e:
                logger.error("Failed to check status of QuasiLattice service.")
                if logger.getEffectiveLevel() <= 10:
                    raise e
    else:
        try:
            subprocess.run([*systemctl, "--no-pager", "-l", "status", SERVICE_NAME], check=False)
        except Exception as e:
            logger.error("Failed to check status of QuasiLattice service.")
            if logger.getEffectiveLevel() <= 10:
                raise e

def _launchd_domain() -> str:
    return f"gui/{os.getuid()}"
 
def _launchd_target() -> str:
    return f"{_launchd_domain()}/{SERVICE_NAME}"
 
def _launchd_service_loaded() -> bool:
    """
    Return True if the launchd service is currently bootstrapped into the
    user's GUI domain.
    """
    result = subprocess.run(
        ["launchctl", "print", _launchd_target()],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
    )
    return result.returncode == 0
 
def setup_launchd_service(system: bool = False):
    if system:
        logger.error("System-wide (daemon) service setup is not supported on macOS.")
        logger.info("Please run without --system.")
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
    plist_path = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents" , f"{SERVICE_NAME}.plist")
    logger.debug(f"Installing service at: {plist_path}")
    os.makedirs(os.path.dirname(plist_path), exist_ok=True)
    with open(plist_path, "w") as plist_file: 
        plist_file.write(plist_content)
    stdout = None if logger.getEffectiveLevel() <= 10 else subprocess.DEVNULL
    domain = _launchd_domain()
    target = _launchd_target()
    if _launchd_service_loaded():
        subprocess.run(["launchctl", "bootout", target], check=False, stdout=stdout, stderr=stdout)
    try:
        subprocess.run(["launchctl", "bootstrap", domain, str(plist_path)], check=True, stdout = stdout, stderr = stdout)
        # `enable` clears any persistent "disabled" override left behind by a
        # prior `launchctl disable`, so the service isn't silently skipped.
        subprocess.run(["launchctl", "enable", target], check=False, stdout = stdout, stderr = stdout)
    except subprocess.CalledProcessError as e:
        logger.error("Failed to setup the QuasiLattice service.")
        if "Could not find domain for" in str(e):
            logger.info("Make sure you are logged into a GUI session (not just SSH'd in) and try again.")
        if logger.getEffectiveLevel() <= 10:
            raise e
        return
    logger.debug("QuasiLattice service setup successfully!")
 
def remove_launchd_service(system: bool = False):
    if system:
        logger.error("System-wide (daemon) service removal is not supported on macOS.")
        logger.info("Please run without --system.")
        return
    plist_path = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents" , f"{SERVICE_NAME}.plist")
    if not os.path.isfile(plist_path):
        logger.info(f"No service found at {plist_path}")
        logger.info("Nothing to remove.")
        return
    logger.debug(f"Removing service from: {plist_path}")
    stdout = None if logger.getEffectiveLevel() <= 10 else subprocess.DEVNULL
    if _launchd_service_loaded():
        try:
            subprocess.run(["launchctl", "bootout", _launchd_target()], check=True, stdout = stdout, stderr = stdout)
        except Exception as e:
            logger.error("Failed to unload the QuasiLattice service.")
            if logger.getEffectiveLevel() <= 10:
                raise e
    os.unlink(plist_path)
    logger.debug("QuasiLattice service removed.")
 
def start_launchd_service(system: bool = False):
    if system:
        logger.error("System-wide (daemon) service management is not supported on macOS.")
        logger.info("Please run without --system.")
        return
    plist_path = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents" , f"{SERVICE_NAME}.plist")
    if not os.path.isfile(plist_path):
        logger.error("QuasiLattice service is not setup.")
        logger.info("You can install it by running: quasilattice setup")
        return
    stdout = None if logger.getEffectiveLevel() <= 10 else subprocess.DEVNULL
    target = _launchd_target()
    if _launchd_service_loaded():
        try:
            subprocess.run(["launchctl", "kickstart", "-k", target], check=True, stdout = stdout, stderr = stdout)
        except Exception as e:
            logger.error("Failed to start QuasiLattice service.")
            if logger.getEffectiveLevel() <= 10:
                raise e
            return
    else:
        try:
            subprocess.run(["launchctl", "bootstrap", _launchd_domain(), str(plist_path)], check=True, stdout = stdout, stderr = stdout)
            subprocess.run(["launchctl", "enable", target], check=False, stdout = stdout, stderr = stdout)
        except Exception as e:
            logger.error("Failed to start QuasiLattice service.")
            if logger.getEffectiveLevel() <= 10:
                raise e
            return
    logger.debug("QuasiLattice service started.")
 
def stop_launchd_service(system: bool = False):
    if system:
        logger.error("System-wide (daemon) service management is not supported on macOS.")
        logger.info("Please run without --system.")
        return
    plist_path = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents" , f"{SERVICE_NAME}.plist")
    if not os.path.isfile(plist_path):
        logger.error("QuasiLattice service is not setup.")
        logger.info("You can install it by running: quasilattice setup")
        return
    if not _launchd_service_loaded():
        logger.debug("QuasiLattice service is already stopped.")
        return
    stdout = None if logger.getEffectiveLevel() <= 10 else subprocess.DEVNULL
    try:
        subprocess.run(["launchctl", "bootout", _launchd_target()], check=True, stdout = stdout, stderr = stdout)
    except Exception as e:
        logger.error("Failed to stop QuasiLattice service.")
        if logger.getEffectiveLevel() <= 10:
            raise e
        return
    logger.debug("QuasiLattice service stopped.")
 
def status_launchd_service(system: bool = False):
    if system:
        logger.error("System-wide (daemon) service management is not supported on macOS.")
        logger.info("Please run without --system.")
        return
    plist_path = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents" , f"{SERVICE_NAME}.plist")
    if not os.path.isfile(plist_path):
        logger.error("QuasiLattice service is not setup.")
        logger.info("You can install it by running: quasilattice setup")
        return
    result = subprocess.run(["launchctl", "print", _launchd_target()], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logger.error("QuasiLattice service is setup but not currently running.")
        return
    logger.info(result.stdout.strip())

def get_windows_executable() -> str:
    """
    Return the path to pythonw.exe if available, so the scheduled task
    runs without popping up a console window. Falls back to sys.executable
    if pythonw.exe can't be found.
    """
    pythonw_path = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if os.path.isfile(pythonw_path):
        return str(pythonw_path)
    return sys.executable

def setup_windows_service(system: bool = False):
    if system:
        logger.warning("--system is not used on Windows; the scheduled task runs at user logon regardless.")
    windows_exe = get_windows_executable()
    logger.debug(f"Using exe: {windows_exe}")
    result = subprocess.run(
        ["schtasks", "/Create", "/SC", "ONLOGON", "/RL", "HIGHEST", "/TN", SERVICE_NAME,
         "/TR", f'"{windows_exe}" -m quasilattice run', "/F"],
        capture_output=True, text=True, check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        logger.error("Failed to setup the QuasiLattice service:")
        logger.info((result.stderr or result.stdout).strip())
        return
    logger.debug("QuasiLattice service setup successfully!")

def remove_windows_service(system: bool = False):
    if system:
        logger.warning("--system is not used on Windows.")
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", SERVICE_NAME, "/F"],
        capture_output=True, text=True, check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        if ("The system cannot find the file specified." in (result.stderr or result.stdout).strip()):
            logger.debug("Failed to remove the QuasiLattice service:")
            logger.debug((result.stderr or result.stdout).strip())
            logger.error("QuasiLattice service is not setup.")
            logger.info("Nothing to remove.")
        else:
            logger.error("Failed to remove the QuasiLattice service:")
            logger.error((result.stderr or result.stdout).strip())
        return
    logger.debug("QuasiLattice service removed.")

def start_windows_service(system: bool = False):
    if system:
        logger.warning("--system is not used on Windows.")
    result = subprocess.run(
        ["schtasks", "/Run", "/TN", SERVICE_NAME],
        capture_output=True, text=True, check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        if ("The system cannot find the file specified." in (result.stderr or result.stdout).strip()):
            logger.debug("Failed to start the QuasiLattice service:")
            logger.debug((result.stderr or result.stdout).strip())
            logger.error("QuasiLattice service is not setup.")
            logger.info("You can install it by running: quasilattice setup")
        else:
            logger.error("Failed to start the QuasiLattice service:")
            logger.error((result.stderr or result.stdout).strip())
    logger.debug("QuasiLattice service started.")

def stop_windows_service(system: bool = False):
    if system:
        logger.warning("--system is not used on Windows.")
    result = subprocess.run(
        ["schtasks", "/End", "/TN", SERVICE_NAME],
        capture_output=True, text=True, check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        if ("The system cannot find the file specified." in (result.stderr or result.stdout).strip()):
            logger.debug("Failed to stop the QuasiLattice service:")
            logger.debug((result.stderr or result.stdout).strip())
            logger.error("QuasiLattice service is not setup.")
            logger.info("You can install it by running: quasilattice setup")
        else:
            logger.error("Failed to stop the QuasiLattice service:")
            logger.error((result.stderr or result.stdout).strip())
        return
    logger.debug("QuasiLattice service stopped.")

def status_windows_service(system: bool = False):
    if system:
        logger.warning("--system is not used on Windows.")
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", SERVICE_NAME],
        capture_output=True, text=True, check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        if ("The system cannot find the file specified." in (result.stderr or result.stdout).strip()):
            logger.debug((result.stderr or result.stdout).strip())
            logger.error("QuasiLattice service is not setup.")
            logger.info("You can install it by running: quasilattice setup")
        else:
            logger.error((result.stderr or result.stdout).strip())
        return
    logger.info(result.stdout.strip())

def main():
    """Configure and run QuasiLattice from the terminal."""
    parser = argparse.ArgumentParser(
        description="A data analysis, knowledge base, journaling and note taking system."
    )
    parser.set_defaults(func=status)
    parser.add_argument("-d", "--debug", action="store_true", help="Provide debug logging. Equivalent to --log-level 5")
    parser.add_argument("-l", "--log-level", type=int, help="Log level (0-5) determines how much information is logged.")
    parser.add_argument("-s", "--system", action="store_true", help="System service. Requires elevated permissions.")
    parser.add_argument("--config_path", type=str, help="Path to the config file.")
    
    subparsers = parser.add_subparsers(
        dest="command", 
        required=False
    )
    run_subparser: argparse.ArgumentParser = subparsers.add_parser("run", help="Run QuasiLattice in the foreground.")
    run_subparser.set_defaults(func=run)
    run_subparser.add_argument("-d", "--debug", action="store_true", help="Provide debug logging.")
    run_subparser.add_argument("-l", "--log-level", type=int, help="Log level (0-5) determines how much information is logged.")
    run_subparser.add_argument("--config_path",type=str,help="Path to the config file.")

    service_commands = {"setup":setup,"remove":remove,"start":start,"stop":stop,"status":status}
    for service_command, command_func in service_commands.items():
        subparser: argparse.ArgumentParser = subparsers.add_parser(service_command, help=service_command.capitalize()+" the QuasiLattice background service.")
        subparser.set_defaults(func=command_func)
        subparser.add_argument("-d", "--debug", action="store_true", help="Provide debug logging. Equivalent to --log-level 5")
        subparser.add_argument("-l", "--log-level", type=int, help="Log level (0-5) determines how much information is logged.")
        subparser.add_argument("-s", "--system", action="store_true", help="System service. Requires elevated permissions.")
        subparser.add_argument("--config_path", type=str, help="Path to the config file.")

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
import argparse

def setup(args):
    if args.verbose:
        print("EXTRA LOGGY") # TODO: Remove
    from .quasilattice import myfunc
    myfunc()
    print("RUN SETUP") # TODO: Implement

def remove(args):
    print("RUN REMOVE") # TODO: Implement

def start(args):
    print("RUN START") # TODO: Implement

def stop(args):
    print("RUN STOP") # TODO: Implement

def status(args):
    print("RUN STATUS") # TODO: Implement

COMMANDS = {
    "setup": {
        "func": setup,
        "help": "Sets up the QuasiLattice background service on the system.",
    },
    "remove": {
        "func": remove,
        "help": "Removes the QuasiLattice background service from the system.",
    },
    "start": {
        "func": start,
        "help": "Starts the QuasiLattice background service.",
    },
    "stop": {
        "func": stop,
        "help": "Stops the QuasiLattice background service.",
    },
    "status": {
        "func": status,
        "help": "Displays the status of the QuasiLattice background service.",
    },
}

def main():
    """Configure and run QuasiLattice from the terminal."""
    parser = argparse.ArgumentParser(
        description="A data analysis, knowledge base, journaling and note taking system."
    )
    
    subparsers = parser.add_subparsers(
        dest="command", 
        required=True
    )

    for name, meta in COMMANDS.items():
        subparser = subparsers.add_parser(name, help=meta["help"])
        subparser.set_defaults(func=meta["func"])
        subparser.add_argument("-v", "--verbose", action="store_true") # TODO: Decide if we really need this

    args = parser.parse_args()
    args.func(args)
    

"""
Entry point of the app
"""

import sys
import argparse

from py.server import app
from py.db import seed_db


def main(args=None):
    """Entry Point"""
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(description='Command Line Tools for running RNNVis')
    parser.add_argument('method', choices=['server', 'seeddb'],
                        help='sever to run the server, seeddb to initialize db from config files')
    parser.add_argument('--debug', '-d', dest='debug', action='store_const', const=True, default=False,
                        help='set this flag to debug')
    args = parser.parse_args(args)

    if args.method == 'server':
        app.run(debug=args.debug)
    elif args.method == 'seeddb':
        seed_db()


if __name__ == "__main__":
    main()

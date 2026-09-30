import argparse,json
from dataclasses import asdict
from .doctor import run_doctor
from .installer import install
from .runtime import Runtime
from .tui import run as run_tui
from .updater import check as check_update
from .version import __version__
def main(argv=None):
    parser=argparse.ArgumentParser(prog="jervis");parser.add_argument("--version",action="version",version="%(prog)s "+__version__);sub=parser.add_subparsers(dest="command")
    for name in ("run","tui","doctor","install","update-check"):sub.add_parser(name)
    args=parser.parse_args(argv);command=args.command or "tui"
    if command=="run":Runtime().run()
    elif command=="tui":run_tui()
    elif command=="doctor":
        report=run_doctor();print(report.render());raise SystemExit(0 if report.ok else 1)
    elif command=="install":install()
    elif command=="update-check":print(json.dumps(asdict(check_update()),indent=2))
if __name__=="__main__":main()

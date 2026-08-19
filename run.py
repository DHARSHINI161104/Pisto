"""Entry point: start the camera pipeline and the web server."""

import argparse
import os
import sys

import config
from app import db, pipeline
from app.server import create_app


def main():
    parser = argparse.ArgumentParser(description="Rifle Club Target Score Display")
    parser.add_argument("--host", default=config.HOST)
    parser.add_argument("--port", type=int, default=config.PORT)
    parser.add_argument("--no-camera", action="store_true",
                        help="Start in manual-entry mode even if a camera exists")
    args = parser.parse_args()

    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    db.init_db()

    if args.no_camera:
        os.environ["RIFLE_DISABLE_CAMERA"] = "1"
    pipeline.start()

    app = create_app()
    print(f"\n  Rifle score display running: http://{args.host}:{args.port}")
    print(f"  Scoreboard:  /display   |  Print target:  /print/target")
    print(f"  Today's results: /results/today\n")
    app.run(host=args.host, port=args.port, debug=config.DEBUG,
            threaded=True)


if __name__ == "__main__":
    sys.exit(main())
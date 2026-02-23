"""
Run the LEGO Factory application.

Usage:
    python run.py [--port PORT] [--host HOST] [--debug]
"""
import argparse
from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='LEGO Factory v3')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    socketio.run(app, host=args.host, port=args.port, debug=args.debug,
                 use_reloader=args.debug, allow_unsafe_werkzeug=True)

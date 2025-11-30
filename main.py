#!/usr/bin/env python3
"""
Ski Resort Parking Monitor - Main Entry Point

This is the main driver script for the ski resort parking monitoring system.
It runs the Flask web application.

Usage:
    python main.py
"""

import argparse
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Ski Resort Parking Monitor")
    
    # Web app specific arguments
    parser.add_argument("--host", default="0.0.0.0", help="Web app host")
    parser.add_argument("--port", type=int, default=5000, help="Web app port")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    from webapp.app import create_app
    app = create_app()
    print(f"🚀 Starting Ski Parking Monitor Web App...")
    print(f"📍 Server running at: http://{args.host}:{args.port}")
    print(f"🔧 Debug mode: {'ON' if args.debug else 'OFF'}")
    app.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()

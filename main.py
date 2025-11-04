#!/usr/bin/env python3
"""
Ski Resort Parking Monitor - Main Entry Point

This is the main driver script for the ski resort parking monitoring system.
It can run in two modes:
1. CLI mode: Direct monitoring with command line arguments
2. Web app mode: Start the Flask web application

Usage:
    python main.py --mode cli --resort brighton --date "2025-03-16"
    python main.py --mode webapp
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

def main():
    parser = argparse.ArgumentParser(description="Ski Resort Parking Monitor")
    parser.add_argument(
        "--mode", 
        choices=["cli", "webapp"], 
        default="cli",
        help="Run mode: cli for command line monitoring, webapp for web interface"
    )
    
    # CLI specific arguments
    parser.add_argument("--resort", help="Resort name (e.g., brighton, solitude)")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format")
    parser.add_argument("--email", help="Email for notifications")
    parser.add_argument("--interval", type=int, default=10, help="Check interval in seconds")
    
    # Web app specific arguments
    parser.add_argument("--host", default="0.0.0.0", help="Web app host")
    parser.add_argument("--port", type=int, default=5000, help="Web app port")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    if args.mode == "cli":
        from monitoring.cli_monitor import run_cli_monitor
        run_cli_monitor(args)
    elif args.mode == "webapp":
        from webapp.app import create_app
        app = create_app()
        print(f"🚀 Starting Ski Parking Monitor Web App...")
        print(f"📍 Server running at: http://{args.host}:{args.port}")
        print(f"🔧 Debug mode: {'ON' if args.debug else 'OFF'}")
        app.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()

"""Entry point for Graph TUI application."""

import sys
import asyncio


def main():
    """Main entry point."""
    try:
        app = GraphTUIApp()
        app.run()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
"""
CLI entry point to start a conversation session directly.

Usage:
    python run_conversation.py              # Start as 'Unknown'
    python run_conversation.py --user Peter # Start as 'Peter'
"""

import argparse
from dotenv import load_dotenv

load_dotenv()

from conversation import ConversationManager


def main():
    parser = argparse.ArgumentParser(description="Start a sharing station conversation")
    parser.add_argument("--user", default="Peter", help="User name for the session")
    args = parser.parse_args()

    cm = ConversationManager()
    print(f"Starting conversation as '{args.user}'... Press Ctrl+C to stop.")
    try:
        cm.start(user_name=args.user)
        cm.wait()
    except KeyboardInterrupt:
        print("\nStopping conversation...")
        cm.stop()


if __name__ == "__main__":
    main()

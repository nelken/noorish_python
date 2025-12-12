import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any
from http.server import BaseHTTPRequestHandler
from openai import OpenAI
import os
import dotenv

try:
    from api.conversation_state import ConversationState
    from api.theme_state import ThemeState
except ImportError:
    from conversation_state import ConversationState
    from theme_state import ThemeState

ROOT_DIR = Path(__file__).resolve().parent.parent
dotenv.load_dotenv(ROOT_DIR / ".env.local")
dotenv.load_dotenv(ROOT_DIR / ".env")

with open('api/burnout-prompt.txt') as f:
    burnout_prompt = f.read()

def get_burnout(state: ConversationState, theme_state: ThemeState) -> str:
    pass

def main():
    get_burnout(None, None)



if __name__ == '__main__':
    main()
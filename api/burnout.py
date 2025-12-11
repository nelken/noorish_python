import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any
from http.server import BaseHTTPRequestHandler
from openai import OpenAI
import os
import dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
dotenv.load_dotenv(ROOT_DIR / ".env.local")
dotenv.load_dotenv(ROOT_DIR / ".env")

def get_burnout():
    pass
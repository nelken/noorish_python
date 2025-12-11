from types import SimpleNamespace

from api.does_answer import does_answer, too_short
from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()


class FakeCompletions:
    def __init__(self, content: str):
        self._content = content

    def create(self, model, messages, max_tokens, temperature):
        # Mimic the minimal shape returned by the OpenAI client.
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self._content)
                )
            ]
        )


class FakeChat:
    def __init__(self, content: str):
        self.completions = FakeCompletions(content)


class FakeClient:
    def __init__(self, content: str):
        self.chat = FakeChat(content)


def test_returns_true_when_model_says_true():
    client = FakeClient("true")
    assert does_answer(client, "Q?", "A") is True


def test_returns_false_when_model_says_false_with_whitespace_and_caps():
    client = FakeClient(" False ")
    assert does_answer(client, "Q?", "A") is False

def test_partial_answer_returns_true_with_real_model():
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    assert does_answer(client, "When you were feeling wiped out after that experience, which part of you felt the most drained? \
    Was it your patience with others, your physical energy, or perhaps your clarity of thought? I'd love to hear your thoughts on this.",
    "patience with others, your physical energy") is True

def test_too_short_returns_true():
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    assert too_short(client, "When you were feeling wiped out after that experience, which part of you felt the most drained? \
    Was it your patience with others, your physical energy, or perhaps your clarity of thought? I'd love to hear your thoughts on this.",
    "physocal") is True

def test_name_too_short_returns_true():
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    assert too_short(client, "What's your name", "Rani") is False

def test_irrelevant_answer_returns_false_with_real_model():
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    assert does_answer(client, "When you were feeling wiped out after that experience, which part of you felt the most drained? \
    Was it your patience with others, your physical energy, or perhaps your clarity of thought? I'd love to hear your thoughts on this.",
     "I like turtles") is False

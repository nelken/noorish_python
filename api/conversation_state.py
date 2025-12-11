from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ConversationState:
    questions: List[str]
    current_index: int = 0
    answers: Dict[int, str] = field(default_factory=dict)
    awaiting_answer: bool = True
    did_answer: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the conversation state into a JSON-friendly dict."""
        return {
            "questions": self.questions,
            "current_index": self.current_index,
            "answers": self.answers,
            "awaiting_answer": self.awaiting_answer,
            "did_answer": self.did_answer,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationState":
        """Rehydrate state from a dict that may have stringified keys."""
        questions = data.get("questions") or []

        answers_raw = data.get("answers") or {}
        answers = {}
        for k, v in answers_raw.items():
            try:
                answers[int(k)] = v
            except ValueError:
                continue

        awaiting_raw = data.get("awaiting_answer", None)
        if awaiting_raw is None:
            awaiting_raw = True if not answers else False

        return cls(
            questions=questions,
            current_index=int(data.get("current_index", 0)),
            answers=answers,
            awaiting_answer=bool(awaiting_raw),
            did_answer=bool(data.get("did_answer", False)),
        )

    @property
    def complete(self) -> bool:
        return self.current_index >= len(self.questions)

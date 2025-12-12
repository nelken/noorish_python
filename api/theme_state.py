from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from api.conversation_state import ConversationState
except ImportError:
    from conversation_state import ConversationState


@dataclass
class ThemeState:
    themes: List[str]
    theme_questions: List[List[str]]
    current_theme_index: int = 0
    themes_addressed: Dict[int, str] = field(default_factory=dict)
    conversations: Dict[int, ConversationState] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "themes": self.themes,
            "theme_questions": self.theme_questions,
            "current_theme_index": self.current_theme_index,
            "themes_addressed": self.themes_addressed,
            "conversations": {
                idx: conv.to_dict() for idx, conv in self.conversations.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ThemeState":
        themes = data.get("themes", []) or []
        theme_questions = [q_list or [] for q_list in (data.get("theme_questions") or [])]
        convs_raw = data.get("conversations") or {}
        convs: Dict[int, ConversationState] = {}
        for idx_str, conv_data in convs_raw.items():
            try:
                idx = int(idx_str)
                convs[idx] = ConversationState.from_dict(conv_data)
            except (ValueError, TypeError):
                continue
        return cls(
            themes=themes,
            theme_questions=theme_questions,
            current_theme_index=int(data.get("current_theme_index", 0)),
            themes_addressed={int(k): v for k, v in (data.get("themes_addressed") or {}).items()},
            conversations=convs,
        )

    @property
    def current_theme(self) -> str:
        if 0 <= self.current_theme_index < len(self.themes):
            return self.themes[self.current_theme_index]
        return ""

    @property
    def current_questions(self) -> List[str]:
        if 0 <= self.current_theme_index < len(self.theme_questions):
            return self.theme_questions[self.current_theme_index] or []
        return []

    def has_more_themes(self) -> bool:
        return self.current_theme_index < len(self.theme_questions) - 1

    def mark_current_addressed(self) -> None:
        if (
            0 <= self.current_theme_index < len(self.themes)
            and self.current_theme_index not in self.themes_addressed
        ):
            self.themes_addressed[self.current_theme_index] = self.themes[self.current_theme_index]

    def advance_theme(self) -> None:
        self.current_theme_index += 1

    def set_conversation_state(self, index: int, conversation: ConversationState) -> None:
        if index >= 0:
            self.conversations[index] = conversation

    def get_conversation_state(self, index: int) -> Optional[ConversationState]:
        return self.conversations.get(index)

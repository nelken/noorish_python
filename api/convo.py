import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any
from http.server import BaseHTTPRequestHandler
from openai import OpenAI
import os
import dotenv
try:
    from api.does_answer import does_answer, too_short
except ImportError:
    from does_answer import does_answer, too_short

# Load .env.local first (local dev) and fall back to a standard .env if present.
ROOT_DIR = Path(__file__).resolve().parent.parent
dotenv.load_dotenv(ROOT_DIR / ".env.local")
dotenv.load_dotenv(ROOT_DIR / ".env")

@dataclass
class ConversationState:
    themes: List[str]
    theme_questions: List[List[str]]
    questions: List[str]
    current_index: int = 0
    answers: Dict[int, str] = field(default_factory=dict)
    themes_addressed: Dict[int, str] = field(default_factory=dict)
    awaiting_answer: bool = True
    did_answer: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the conversation state into a JSON-friendly dict."""
        return {
            "themes": self.themes, 
            "theme_questions": self.theme_questions,
            "questions": self.questions,
            "current_index": self.current_index,
            "answers": self.answers,
            "themes_addressed": self.themes_addressed,
            "awaiting_answer": self.awaiting_answer,
            "did_answer": self.did_answer
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationState":
        """Rehydrate state from a dict that may have stringified keys."""
        answers_raw = data.get("answers") or {}
        answers = {int(k): v for k, v in answers_raw.items()}
        
        themes_addressed_raw = data.get("themes_addressed") or {}
        themes_addressed = {int(k): v for k, v in themes_addressed_raw.items()}

        theme_questions = data.get("theme_questions", [])

        awaiting_raw = data.get("awaiting_answer", None)
        if awaiting_raw is None:
            awaiting_raw = True if not answers else False
        return cls(
            themes=data.get("themes", []),            
            theme_questions=theme_questions,
            questions=data.get("questions", []),
            current_index=int(data.get("current_index", 0)),
            answers=answers,
            themes_addressed=themes_addressed,
            awaiting_answer=bool(awaiting_raw),
            did_answer=bool(data.get("did_answer", False)),
        )

    @property
    def complete(self) -> bool:
        return self.current_index >= len(self.questions)



def build_prompt(state: ConversationState, user_message: str) -> str:
    """
    Build an instruction for the LLM.
    The LLM's goal is to be friendly but always move toward the next question.
    """
    # Current and remaining questions
    if state.complete:
        current_q = None
        remaining = []
    else:
        current_q = state.questions[state.current_index]
        remaining = state.questions[state.current_index + 1:]

    previous_qas = [
        f"Q: {state.questions[i]}\nA: {a}"
        for i, a in state.answers.items()
    ]
    previous_block = "\n\n".join(previous_qas) if previous_qas else "None yet."

    prompt = f"""
        You are a super emphathtic and highly emotionally intelligent interviewer running a structured conversation.
        Your main goal is to make sure the user answers each question in a list of questions.
        When you get a reply from a user to an answer, apply your best judgement to determine whether the user actually addressed the question or not. 

        Be warm and conversational. Acknowledge what the user said. 

        Conversation context:
        Previous questions and answers:
        {previous_block}

        Last user message:
        {user_message}

        {"All questions have already been answered. Thank the user and briefly summarize their answers." if state.complete else ""}

        {"Current question you want them to answer next: " + current_q if current_q else ""}

        Remaining questions after that:
        {remaining}

        Instructions:
        - If there is a current question, make sure your reply clearly includes a paraphrase of that question in natural language. 
        - Do not repeat the question verbatim. Instead rephrase it differently but keep the same meaning. 
        - If the user answers very shortly ask for clarification
        """
    return prompt.strip()

def handle_turn(state: ConversationState, user_message: str) -> tuple[str, ConversationState]:
    """
    Update state with the latest user response. Then ask the next question conversationally.
    """
    # Only record an answer if we previously asked for one
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    # If this is the very first turn and no flag was set, expect an answer
    if not state.awaiting_answer and not state.answers and state.current_index == 0:
        state.awaiting_answer = True

    if (
        state.awaiting_answer
        and not state.complete
        and state.current_index not in state.answers
    ):
        # if too_short(client, state.questions[state.current_index], user_message):
        #     state.did_answer = False
        #     if not state.current_index in state.answers:
        #         state.answers[state.current_index] = ''
        #     state.answers[state.current_index] += ' ' + user_message + ". "
        #     return "thanks for sharing that, do you mind elaborating a bit?", state
        if does_answer(client, state.questions[state.current_index], user_message):
            state.answers[state.current_index] = user_message + '.'
            state.current_index += 1
            state.did_answer = True
        else:
            state.did_answer = False
    # Reset flag until we ask something new
    #state.awaiting_answer = False

    # Build system-style prompt
    prompt = build_prompt(state, user_message)

    # Call the model. Using chat completions for stability on Vercel.
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    bot_reply = response.choices[0].message.content

    # We just asked the next question (if any); expect an answer next turn
    state.awaiting_answer = not state.complete

    if state.complete:
        bot_reply += " Thanks for completing the survey, next steps to follow..."

    return bot_reply, state

    
class handler(BaseHTTPRequestHandler):
    # Vercel may return errors before hitting handler methods; ensure CORS on all paths.
    server_version = "NoorishServer/1.0"

    def end_headers(self):
        # Always attach CORS headers, even on errors.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"

        conversation_state = ConversationState(themes=[], theme_questions=[], questions=[])
        try:
            data = json.loads(body.decode("utf-8"))
            user_message = data.get("content", "")
            raw_state = data.get("conversation_state", {})
            if isinstance(raw_state, str):
                raw_state = json.loads(raw_state or "{}")
            conversation_state = ConversationState.from_dict(raw_state)            
        except Exception as exc:
            # If parsing fails for any other reason, surface a clear error
            self._set_headers(400)
            self.wfile.write(
                json.dumps({"error": f"Invalid request: {exc}"}).encode("utf-8")
            )
            return

        try:
            reply, new_state = handle_turn(conversation_state, user_message)
            #print("new_state", new_state)
            self._set_headers(200)
            self.wfile.write(
                json.dumps(
                    {"content": reply, "conversation_state": new_state.to_dict()}
                ).encode("utf-8")
            )
        except Exception as exc:
            # Always return CORS headers, even on failure
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

def main():
    themes=["Exhaustion", "Depersonalization", "Professional efficacy"]
    questions = [
      'Tell me about the last time you felt completely wiped out. What was happening that day?',
      'When you hit that wiped-out feeling, what drains fastest: your patience with people, your physical energy, or your ability to think clearly?',
      'These days, what part of work makes you want to just check out or stop caring?',
      'When you think about your actual skills and what you can do—not how you feel—how confident are you that you\'re still good at your work?',
      'Looking back over the last few months, is this feeling getting better, staying the same, or getting worse?'
    ]
    theme_questions = [
        # Exhaustion
        ['Tell me about the last time you felt completely wiped out. What was happening that day?', 
         'When you hit that wiped-out feeling, what drains fastest: your patience with people, your physical energy, or your ability to think clearly?'],
        # Depersonalization
        ['These days, what part of work makes you want to just check out or stop caring?'],
        # Professional efficacy
        ['When you think about your actual skills and what you can do—not how you feel—how confident are you that you\'re still good at your work?',
         'Looking back over the last few months, is this feeling getting better, staying the same, or getting worse?']
    ]


    state = ConversationState(themes=themes, theme_questions=theme_questions, questions=questions)

    print("Bot: Hi, I’d love to ask you a few questions to understand your situation better.")

    while True:
        user_message = input("You: ")

        bot_reply, state = handle_turn(state, user_message)
        print("Bot:", bot_reply)
        print("state", state.to_dict())

        if state.complete:
            print("\nBot: That was the last question. Thanks for sharing all of that with me.")
            break

if __name__ == "__main__":
    main()

import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler
from openai import OpenAI
import os
import dotenv

try:
    from api.conversation_state import ConversationState
    from api.theme_state import ThemeState
    from api.does_answer import does_answer, too_short
    from api.burnout import get_burnout
except ImportError:
    from conversation_state import ConversationState
    from theme_state import ThemeState
    from does_answer import does_answer, too_short
    from burnout import get_burnout

# Load .env.local first (local dev) and fall back to a standard .env if present.
ROOT_DIR = Path(__file__).resolve().parent.parent
dotenv.load_dotenv(ROOT_DIR / ".env.local")
dotenv.load_dotenv(ROOT_DIR / ".env")

def build_prompt(state: ConversationState, theme_state: ThemeState, user_message: str) -> str:
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

    current_theme = theme_state.current_theme if not state.complete else theme_state.current_theme

    previous_qas = []
    for i in sorted(state.answers.keys()):
        a = state.answers[i]
        question = state.questions[i] if i < len(state.questions) else f"Question {i + 1}"
        theme_label = theme_state.current_theme
        if theme_label:
            previous_qas.append(f"[{theme_label}] Q: {question}\nA: {a}")
        else:
            previous_qas.append(f"Q: {question}\nA: {a}")
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

        {"Current theme: " + current_theme if current_theme else ""}

        {"Current question you want them to answer next: " + current_q if current_q else ""}

        Remaining questions after that:
        {remaining}

        Instructions:
        - If there is a current question, make sure your reply clearly includes a paraphrase of that question in natural language. 
        - Do not repeat the question verbatim. Instead rephrase it differently but keep the same meaning. 
        - If the user answers very shortly ask for clarification
        """
    return prompt.strip()

def handle_turn(state: ConversationState, theme_state: ThemeState, user_message: str) -> tuple[str, ConversationState, ThemeState]:
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

    # If we finished this theme and there is another theme, move to the next one
    if state.complete:
        theme_state.mark_current_addressed()
        if theme_state.has_more_themes():
            theme_state.advance_theme()
            state = ConversationState(
                questions=theme_state.current_questions,
                current_index=0,
                answers={},
                awaiting_answer=True,
                did_answer=False,
            )
    # Build system-style prompt
    prompt = build_prompt(state, theme_state, user_message)

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

    return bot_reply, state, theme_state

    
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

        conversation_state = ConversationState(questions=[])
        theme_state = ThemeState(themes=[], theme_questions=[])
        try:
            data = json.loads(body.decode("utf-8"))
            user_message = data.get("content", "")
            raw_state = data.get("conversation_state", {})
            raw_theme = data.get("theme_state", {})
            if isinstance(raw_state, str):
                raw_state = json.loads(raw_state or "{}")
            if isinstance(raw_theme, str):
                raw_theme = json.loads(raw_theme or "{}")
            conversation_state = ConversationState.from_dict(raw_state)
            theme_state = ThemeState.from_dict(raw_theme)

            # If no questions present, pull them from the current theme.
            if not conversation_state.questions and theme_state.theme_questions:
                conversation_state.questions = theme_state.current_questions
        except Exception as exc:
            # If parsing fails for any other reason, surface a clear error
            self._set_headers(400)
            self.wfile.write(
                json.dumps({"error": f"Invalid request: {exc}"}).encode("utf-8")
            )
            return

        try:
            reply, new_state, new_theme_state = handle_turn(conversation_state, theme_state, user_message)
            #print("new_state", new_state)
            self._set_headers(200)
            self.wfile.write(
                json.dumps(
                    {
                        "content": reply,
                        "conversation_state": new_state.to_dict(),
                        "theme_state": new_theme_state.to_dict(),
                    }
                ).encode("utf-8")
            )
        except Exception as exc:
            # Always return CORS headers, even on failure
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

def main():
    themes=["Exhaustion", "Depersonalization", "Professional efficacy"]
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
    theme_state = ThemeState(themes=themes, theme_questions=theme_questions)
    
    state = ConversationState(questions=theme_state.current_questions)

    print("Bot: Hi, I’d love to ask you a few questions to understand your situation better.")

    while True:
        user_message = input("You: ")

        bot_reply, state, theme_state = handle_turn(state, theme_state, user_message)
        print("Bot:", bot_reply)
        #print("state", state.to_dict())

        if state.complete:
            print("\nBot: That was the last question. Thanks for sharing all of that with me.")
            print(get_burnout(state))


if __name__ == "__main__":
    main()

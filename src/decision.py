import os
import json
from typing import List

import google.generativeai as genai
from dotenv import load_dotenv
from pydantic import ValidationError

from src.retrieval import retrieve
from src.schemas import AIDecision

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

DECISION_MODEL = "models/gemini-3.6-flash"

VALID_ACTIONS = [
    "APPROVE_REFUND",
    "APPROVE_REPLACEMENT",
    "REQUEST_PHOTOS",
    "DENY",
    "ESCALATE",
    "NEEDS_MORE_INFORMATION",
]

SYSTEM_PROMPT = f"""You are a support-ticket decision assistant. You will be given
a customer's support ticket message and relevant excerpts from company policy
documents. Based ONLY on the provided policy context, decide what action should
be taken.

Valid actions: {', '.join(VALID_ACTIONS)}

Rules:
- Base your decision strictly on the provided policy context. Do not invent
  policy details that are not present in the context.
- If the ticket does not contain enough information to make a confident
  decision (e.g. missing order value, missing timeframe), use
  NEEDS_MORE_INFORMATION rather than guessing.
- "sources" must list only the filenames of the policy documents you actually
  used from the provided context.
- "confidence" must be a number between 0.0 and 1.0 reflecting how well the
  policy context supports your decision.

Respond with ONLY a JSON object in this exact format, no other text:
{{
  "action": "<one of the valid actions>",
  "confidence": <float 0.0-1.0>,
  "reason": "<brief explanation grounded in the policy context>",
  "sources": ["<filename1>", "<filename2>"]
}}
"""


def build_prompt(ticket_message: str, context_chunks: List[tuple]) -> str:
    context_text = "\n\n".join(
        f"[Source: {source}]\n{chunk}" for chunk, source, _ in context_chunks
    )
    return f"""Policy context:
{context_text}

Customer ticket:
{ticket_message}

Based on the policy context above, provide your decision as a JSON object."""


def make_decision(ticket_message: str, k: int = 3) -> AIDecision:
    """
    Runs the full pipeline: retrieve relevant policy chunks, call the LLM,
    parse and validate the response against the AIDecision schema.
    Falls back to NEEDS_MORE_INFORMATION if the LLM output is invalid.
    """
    context_chunks = retrieve(ticket_message, k=k)
    prompt = build_prompt(ticket_message, context_chunks)

    model = genai.GenerativeModel(
        model_name=DECISION_MODEL,
        system_instruction=SYSTEM_PROMPT,
    )
    response = model.generate_content(prompt)

    raw_text = response.text.strip()
    # Strip markdown code fences if the model wraps its JSON in them
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        data = json.loads(raw_text)
        decision = AIDecision(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        # LLM returned malformed or invalid output — fail safe
        decision = AIDecision(
            action="NEEDS_MORE_INFORMATION",
            confidence=0.0,
            reason=f"AI response could not be parsed or validated: {e}",
            sources=[],
        )

    return decision


if __name__ == "__main__":
    # Quick manual test: run `python -m src.decision` from project root
    test_ticket = "My order arrived damaged. It cost around 3000 rupees. What should I do?"
    result = make_decision(test_ticket)
    print(result.model_dump_json(indent=2))
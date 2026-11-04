"""Chainlit entry point. Run with: chainlit run app/main.py"""

import sys
from pathlib import Path

# chainlit run only puts app/ on the import path, so `from app...` needs the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chainlit as cl  # noqa: E402

from app.schemas import ParsedRequest  # noqa: E402, F401 - proves the app package imports


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Placeholder until the App role wires up the pipeline."""
    await cl.Message(content="The shopping copilot isn't wired up yet.").send()

# Decisions made without Or

Each entry: what was decided, why, and what else was considered. The Lead keeps this log and reports new entries at the end of each wave.

## Wave 0

- **Eval labels for the new language cases.** Added Hebrew and Spanish rows to `datasets/`, with Hebrew chosen because Bazak is Israeli. Alternative: test only Spanish, which would miss right-to-left text.
- **Grounding score covers titles and money amounts only.** Other numbers are printed for Or to read. Alternative: an allow-list for every number, which failed true replies such as "5 laptops; here are 3".
- **Reply language is checked with Hebrew script and short stopword lists.** Alternative: a language detection library, which adds a dependency for 4 eval cases.
- **Show more makes no LLM call.** It only adds cards, so it needs no language. Alternative: pass the last typed message to the responder, which costs a call for no new information.
- **Chainlit stays after the mobile test.** At 375px in headless Chromium, the login, chat, past-chats drawer and resuming a chat all worked with no sideways scrolling. One early run clicked the sidebar button and no drawer appeared; it worked in every later run and wasn't explained, so Or's phone-width check in wave 3 should try it. Alternative: switch frameworks, which the test gave no reason to do.
- **Hebrew needs CSS.** In the same test, a Hebrew reply rendered left-to-right with its punctuation misplaced. The App role fixes this in Step 5.
- **`app/main.py` adds the repo root to `sys.path`.** `chainlit run` only puts `app/` on the path, so `from app...` failed. Alternative: run from another layout, which would move every module for one import.
- **`app/llm.py` holds the real OpenAI client, owned by the LLM role.** Keeping it separate means the other modules and all tests only see a plain callable.
- **Pinned the direct dependencies** to the tested versions, so a stranger's install matches.

---
name: todo-triage
description: "Walks TODO.md with the user in rounds of multiple-choice questions, each with a recommended answer, then applies the answers to TODO.md: ticks or closes done items, deletes stale ones, splits big ones, records decisions, sets priorities and picks the next item to work. Use when the user asks to go through, triage, clean up or prioritise TODO.md, or asks what to work on next."
---

# Triaging TODO.md with the user

The user decides; you prepare the choices and write the result. Entry formats and how to close an entry are in the `record-keeping` skill and the project's `AGENTS.md`.

## Steps

1. **List the open items.** Never open `TODO.md` whole. Run:

   ```sh
   rg -n '^#{2,3} |^- \[ \]' TODO.md | cut -c1-220
   ```

   If the user named a section or keyword, keep only what matches. Read one entry in full only when its first line does not tell you what it asks.

2. **Sort each item into one bucket** (keep the list to yourself):

   | Bucket | Sign |
   |---|---|
   | Done already | `git log --oneline -20`, `rg` on the named file or symbol, or `python3 scripts/changelog.py --r START:` shows it landed |
   | Stale | names a file, folder or feature that no longer exists, or a decision since taken |
   | Decision | says "decide", "ask", "choose", has two options, or its Blocker is a decision |
   | Too big | several numbered parts, more than one area, or Effort `>1d` |
   | Ready | one clear step, nothing blocking it |

   Check a "Done already" or "Stale" guess with one command before you ask about it.

3. **Ask in rounds** with your multiple-choice question tool (`AskUserQuestion` in Claude Code; elsewhere, a numbered list the user answers by number). Up to 4 questions a round, the most valuable first: done/stale confirmations, then decisions, then splits, then priority. Each question:
   - names the item in plain words and its `TODO.md` line;
   - has 2 to 4 options, the recommended one **first**, labelled `(Recommended)`, with a one-line reason;
   - offers concrete actions: close it, delete it, split into N items (name them), raise or lower its priority, keep, or the decision's options.

   Stop after 3 rounds or when the user says stop. Do not ask what the code or `git log` can answer.

4. **The last round picks the next item to work.** Offer the 3 best `Ready` items, recommended first.

5. **Apply the answers to `TODO.md`:**
   - Keep the file's own format, headers and any ids or markers in comments.
   - Close done items as the `record-keeping` skill says (tick `- [x]`, or remove the entry); delete items the user called stale.
   - A split replaces one item with its parts in the same place.
   - A decision that changes a requirement goes in the doc that owns it, and the task links there instead of restating it.
   - Reword only what the user changed.

6. **Record it.** Commit only `TODO.md` and any doc you edited, then `python3 scripts/changelog.py --w "todo: <what the triage changed>"`.

7. **Report** what changed (closed, deleted, split, reprioritised, decided) and the item picked next, and offer to start it.

## Do not

- Close an item because the user guessed; check it, or ask.
- Ask more than 4 questions at once, or a question without a recommended answer.
- Start the picked item before `TODO.md` is committed.

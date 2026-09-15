# Chat reliability upgrade

## Implemented

- User messages render as text. Assistant and widget Markdown use the same
  DOMPurify sanitizer, preserving Markdown and citation links.
- ReAct model streams emit `answer_delta` events. `answer` remains the final,
  authoritative answer for existing clients and conversation persistence.
- Tool rounds count once and allow the configured number of rounds. Thought
  audit entries are no longer duplicated in streaming runs. Finalization omits
  unanswered tool calls from the model request.
- Model usage is summed from provider response metadata and written to
  `AgentRun.total_tokens`. Unknown usage is omitted from SSE, not estimated.
- Disconnects close the nested generators, stop subsequent model/tool steps,
  and mark unfinished runs `cancelled`. Completed runs keep their status.

## Accounting and cancellation boundaries

Usage currently covers the main ReAct model calls and the finalization call.
Embedding, model calls inside tools, and memory summaries are not included.
The RAG savings bar is still a character-based estimate relative to full source
documents; it is not an invoice or a measurement of total monetary savings.
Providers that omit streaming usage cannot provide complete measured usage.

Cancellation is cooperative: an in-flight blocking HTTP call or tool can finish
before observing cancellation. The model client has a 60-second timeout and
bounded retries. Provider billing cannot be cancelled retroactively.
The iteration-limit finalization call currently sends its answer as one event.

## Verification

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_*.py
npm run frontend:build
# With Vite listening on 127.0.0.1:5174:
.venv\Scripts\python.exe scripts/check_markdown_browser.py
```

Next stages: structured document parsing and versioned indexes, then a complete
business workflow with approval and output delivery.

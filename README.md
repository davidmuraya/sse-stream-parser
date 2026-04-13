# sse-stream-parser

A fast, lightweight, and correct Server-Sent Events (SSE) stream parser for Python, designed specifically for async environments.

## Objective

Parsing SSE streams - especially from large language model (LLM) APIs and real-time streaming services - can often be inefficient or fragile. `sse-stream-parser` exists to provide a highly optimized, low-overhead solution that strictly follows the SSE specification while seamlessly integrating with Python's `asyncio` ecosystem.

By taking an `AsyncGenerator[bytes, None]` and yielding parsed text chunks, it makes consuming low-level byte streams completely effortless.

## Features

- **Standard Compliant**: Correctly handles `\n` (LF) and `\r\n` (CRLF) line endings.
- **Robust Parsing**: Ignores comments (lines starting with `:`) and safely skips irrelevant fields like `event:`, `id:`, and `retry:`.
- **High Performance**: Utilizes [`orjson`](https://github.com/ijl/orjson) for extremely fast JSON decoding.
- **Smart Concatenation**: Automatically collects and joins multiple `data:` lines occurring within a single event.
- **LLM Ready**: Automatically extracts the `response` field from JSON payloads natively, and stops gracefully when encountering `[DONE]` messages (a common convention in OpenAI/LLM APIs).
- **Resilient**: Gracefully handles EOF scenarios, even when streams close without trailing newlines.

## Requirements

- Python 3.8+
- `orjson`

## Installation

Ensure you have `orjson` installed in your environment:

```bash
pip install orjson
```

*(Note: If this is published to PyPI as a package, you would simply run `pip install sse-stream-parser`)*

## Usage Example

```python
import asyncio
from typing import AsyncGenerator
from main import parse_sse_stream

# 1. Provide an async byte-stream (e.g., from an HTTP client like httpx or aiohttp)
async def mock_byte_stream() -> AsyncGenerator[bytes, None]:
    yield b'data: {"response": "Hello"}\n\n'
    yield b'data: {"response": " world!"}\n\n'
    yield b'data: [DONE]\n\n'

async def main():
    stream = mock_byte_stream()

    # 2. Parse the stream
    async for text_chunk in parse_sse_stream(stream):
        print(text_chunk, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
```

## How It Works

1. **Buffering**: Reads incoming `bytes` chunks and extends a fast `bytearray` buffer.
2. **Line Parsing**: Scans for standard event boundaries (blank lines).
3. **Extraction**: Isolates `data:` lines and drops prefixes.
4. **Decoding**: Parses collected event data using `orjson.loads()` and yields the inner `"response"` content.
5. **Termination**: Cleanly halts generator execution upon encountering the literal `b"[DONE]"`.

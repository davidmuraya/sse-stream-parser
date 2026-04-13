# ⚡ High-Performance Async SSE Parser

An extremely fast, lightweight, and correct Server-Sent Events (SSE) stream parser for Python, designed specifically for async environments.

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

## Real-World Usage: FastAPI & LLM Chat Streaming

Because `sse-stream-parser` operates entirely asynchronously, it is highly recommended for building streaming endpoints in async web frameworks like **FastAPI**. It allows you to consume a raw byte stream from an upstream provider (like Cloudflare AI, OpenAI, or Anthropic), parse the events on the fly, and stream the generated text directly to your users.

Here is a simplified example of how you can integrate it into a FastAPI application using `httpx`:

```python
import httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from main import parse_sse_stream

app = FastAPI()

async def generate_ai_response(prompt: str):
    async with httpx.AsyncClient() as client:
        # 1. Make a streaming request to an upstream LLM provider
        request_data = {"prompt": prompt, "stream": True}
        async with client.stream("POST", "https://api.example-llm.com/generate", json=request_data) as response:
            
            # 2. Pass the byte stream directly into the parser
            # response.aiter_bytes() yields an AsyncGenerator[bytes, None]
            async for text_chunk in parse_sse_stream(response.aiter_bytes()):
                
                # (Optional) Log, intercept, or process the chunk here
                print(f"Received chunk: {text_chunk}")
                
                # 3. Yield the pure text back to the client
                yield text_chunk

@app.get("/chat")
async def chat_endpoint(prompt: str):
    # Set headers to prevent buffering by proxies like Nginx
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }

    # Stream the parsed responses seamlessly to the end-user
    return StreamingResponse(
        generate_ai_response(prompt),
        headers=headers
    )
```

## How It Works

1. **Buffering**: Reads incoming `bytes` chunks and extends a fast `bytearray` buffer.
2. **Line Parsing**: Scans for standard event boundaries (blank lines).
3. **Extraction**: Isolates `data:` lines and drops prefixes.
4. **Decoding**: Parses collected event data using `orjson.loads()` and yields the inner `"response"` content.
5. **Termination**: Cleanly halts generator execution upon encountering the literal `b"[DONE]"`.

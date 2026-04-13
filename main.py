from typing import AsyncGenerator

import orjson

async def parse_sse_stream(stream: AsyncGenerator[bytes, None]) -> AsyncGenerator[str, None]:
    """
    Parse a byte-oriented Server-Sent Events stream.

    SSE-correct behavior:
    - Supports LF and CRLF line endings.
    - Ignores comment lines starting with ':'.
    - Ignores non-data fields like event:, id:, retry:.
    - Collects multiple data: lines in a single event and joins them with '\n'.
    - Dispatches an event on the blank line separator.
    - Stops when the data payload equals b'[DONE]'.

    This is optimized for low overhead while staying correct for standard SSE.
    """

    buffer = bytearray()
    data_parts: list[bytes] = []

    DATA_PREFIX = b"data:"
    COMMENT_PREFIX = b":"
    CR = 13  # ord('\r')
    LF = 10  # ord('\n')

    def flush_event(parts: list[bytes]) -> tuple[bool, str | None]:
        """
        Turn the collected `data:` lines for one SSE event into a response string.

        Returns:
            - (True, None) when the stream should stop
            - (False, string) when JSON contains a `response` field
            - (False, None) for empty / malformed / non-response events
        """
        if not parts:
            return False, None

        event_data = b"\n".join(parts)
        parts.clear()

        if event_data == b"[DONE]":
            return True, None

        try:
            obj = orjson.loads(event_data)
        except orjson.JSONDecodeError:
            return False, None

        response = obj.get("response")
        if response is None:
            return False, None

        return False, response if isinstance(response, str) else str(response)

    async for chunk in stream:
        if not chunk:
            continue

        buffer.extend(chunk)

        # Parse complete lines from the buffer without repeatedly deleting from the front.
        # We only trim the buffer once after consuming all complete lines.
        search_from = 0

        while True:
            nl_idx = buffer.find(LF, search_from)
            if nl_idx == -1:
                break

            # Strip a trailing CR if the line uses CRLF.
            line_end = nl_idx
            if line_end > search_from and buffer[line_end - 1] == CR:
                line_end -= 1

            line = bytes(buffer[search_from:line_end])
            search_from = nl_idx + 1

            # Blank line = SSE event boundary.
            if not line:
                is_done, text = flush_event(data_parts)
                if is_done:
                    return
                if text is not None:
                    yield text
                continue

            # Comments are legal SSE lines and should be ignored.
            if line.startswith(COMMENT_PREFIX):
                continue

            # Only `data:` lines contribute to the event payload.
            if line.startswith(DATA_PREFIX):
                payload = line[len(DATA_PREFIX) :]
                if payload.startswith(b" "):
                    payload = payload[1:]
                data_parts.append(payload)
                continue

            # Ignore other SSE fields: event:, id:, retry:, etc.
            continue

        # Drop the processed portion of the buffer in one shot.
        if search_from:
            del buffer[:search_from]

    # EOF handling:
    # If the upstream closes without a trailing newline, process the remaining line(s)
    # as best effort and emit the last event if one was in progress.
    if buffer:
        if buffer[-1] != LF:
            buffer.append(LF)

        search_from = 0
        while True:
            nl_idx = buffer.find(LF, search_from)
            if nl_idx == -1:
                break

            line_end = nl_idx
            if line_end > search_from and buffer[line_end - 1] == CR:
                line_end -= 1

            line = bytes(buffer[search_from:line_end])
            search_from = nl_idx + 1

            if not line:
                is_done, text = flush_event(data_parts)
                if is_done:
                    return
                if text is not None:
                    yield text
                continue

            if line.startswith(COMMENT_PREFIX):
                continue

            if line.startswith(DATA_PREFIX):
                payload = line[len(DATA_PREFIX) :]
                if payload.startswith(b" "):
                    payload = payload[1:]
                data_parts.append(payload)

    # Final unterminated event at EOF.
    is_done, text = flush_event(data_parts)
    if is_done:
        return
    if text is not None:
        yield text

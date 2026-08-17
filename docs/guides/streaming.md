---
title: Streaming
description: The server-sent events contract for stream=true, event by event, with complete Python and Node consumers.
---

# Streaming

Set `"stream": true` on [`POST /v1/manifold/messages`](../api/messages.md) and the reply
arrives as server-sent events instead of one JSON body. The request is otherwise
identical, and so is the price.

```json
{
  "model": "nova-micro",
  "max_tokens": 1024,
  "stream": true,
  "messages": [{ "role": "user", "content": "Count to five." }]
}
```

## Response headers

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache
X-Accel-Buffering: no
```

`X-Accel-Buffering: no` tells proxies not to buffer, so deltas reach you as they are
produced. If you put your own proxy in front, make sure it does not buffer either.

## The wire format

Each event is an `event:` line, a `data:` line holding one JSON object, then a blank line.

```text
event: message_start
data: {"id":"mfr_9f7922159e6dab6a72166e1f","model":"nova-micro","role":"assistant"}

event: content_block_delta
data: {"index":0,"delta":{"type":"text_delta","text":"Hello"}}

event: content_block_delta
data: {"index":0,"delta":{"type":"text_delta","text":" from TriStack"}}

event: message_delta
data: {"stop_reason":"end_turn","usage":{"input_tokens":10,"output_tokens":6},"cost":{"paise":1}}

event: message_stop
data: {}
```

There is no `[DONE]` sentinel. `message_stop` is the end of a successful stream.

## The events

| Event | When | Payload |
|---|---|---|
| `message_start` | Once, first | `{ "id", "model", "role" }` |
| `content_block_delta` | Repeatedly | `{ "index", "delta": { "type", "text" } }` |
| `message_delta` | Once, after the last delta | `{ "stop_reason", "usage", "cost" }` |
| `message_stop` | Once, last | `{}` |
| `error` | Replaces `message_delta` and `message_stop` | `{ "error", "code" }` |

Notes that save debugging time:

- **`message_start.id`** is the `mfr_...` request id, the same one your usage rows carry.
  `role` is always `assistant`.
- **Deltas split anywhere.** `delta.text` can end mid-word or mid-sentence, and
  `delta.type` is `text_delta`. Concatenate in arrival order and do not assume token or
  word boundaries.
- **`index` identifies the content block.** Replies carry a single text block today, so it
  is always `0`. Key your accumulator on it anyway and new block types will not break you.
- **`message_delta` carries the money**: `usage` holds `input_tokens` and `output_tokens`,
  `cost` holds `paise`. There is no running cost per delta, and no usage anywhere else in
  the stream.

## Failures

A stream can fail in two places, and they look different on the wire.

**Before the first event.** Nothing has been committed to a stream yet, so the response is
an ordinary JSON error with a real status code: `429 provider_throttled`,
`403 model_access_denied`, `502 provider_error` and so on. Check the status before you
start parsing events.

**Mid-stream.** The response is already `200` with events flowing. The failure arrives as
an `error` event in place of `message_delta` and `message_stop`:

```text
event: error
data: {"error":"The model provider failed mid-stream.","code":"provider_error"}
```

Your consumer must treat "the stream ended without `message_delta`" as a failure, whether
or not it saw an `error` event. That is the one case where you have partial text and no
usage figures.

## Aborting a stream

You can stop reading at any time: close the connection or cancel the request. The
important part is what it costs.

- The call **settles**, it is not free.
- If the model already reported usage, that real usage is billed, exactly as if you had
  read to the end. The request is recorded in usage as a **success**, because it is one:
  the call completed, you just stopped listening.
- If it had not, the settlement is estimated the way the pre-flight hold was estimated:
  the **whole input** at 4 characters per token, plus the output that actually reached
  you, also at 4 characters per token and capped at your `max_tokens`. The rest of the
  hold is returned, and the request is recorded in usage as failed, with the code
  `client_aborted`.
- If you aborted before any text arrived, there is nothing to settle and the whole hold is
  released.

The input side is the part that surprises people: it is charged in full, not in proportion
to how far the reply got. Aborting a call with a long `system` prompt or an image in it is
expensive even when barely any output arrived. See
[what a failure costs](../pricing/billing.md#what-a-failure-costs).

A model failure is different: nothing was delivered that you asked to keep, so the hold is
released in full and the call costs nothing. Only your own abort forfeits the refund on
what already reached you.

## Complete consumers

The wire format is server-sent events, but a browser `EventSource` cannot call this
endpoint: it only issues `GET`, and it cannot set request headers, so neither the API key
nor the JSON body has anywhere to go. Use `fetch`, `httpx`, or any client that can stream
the response of a `POST`, as below.

=== "Python"

    ```python
    # pip install httpx
    import json
    import os
    from typing import Iterator

    import httpx

    API = "https://api.tristack.tech"
    KEY = os.environ["TRISTACK_API_KEY"]


    def stream_message(prompt: str, model: str = "nova-micro") -> Iterator[tuple[str, dict]]:
        """Yields (event_name, payload) pairs until the stream ends."""
        payload = {
            "model": model,
            "max_tokens": 1024,
            "stream": True,
            "messages": [{"role": "user", "content": prompt}],
        }

        with httpx.Client(timeout=httpx.Timeout(120.0, read=None)) as client:
            with client.stream(
                "POST",
                f"{API}/v1/manifold/messages",
                headers={"Authorization": f"Bearer {KEY}"},
                json=payload,
            ) as response:
                if response.status_code != 200:
                    # A failure before the first event is plain JSON, not SSE.
                    response.read()
                    failure = response.json()
                    raise RuntimeError(
                        f"{response.status_code} {failure.get('code', '-')}: "
                        f"{failure.get('error') or failure.get('title')}"
                    )

                event = None
                for line in response.iter_lines():
                    if line.startswith("event: "):
                        event = line[len("event: ") :]
                    elif line.startswith("data: ") and event is not None:
                        yield event, json.loads(line[len("data: ") :])
                    elif not line:
                        event = None


    def main() -> None:
        text = []
        settled = False

        for event, data in stream_message("Count to five."):
            if event == "content_block_delta":
                chunk = data["delta"]["text"]
                text.append(chunk)
                print(chunk, end="", flush=True)
            elif event == "message_delta":
                settled = True
                print(
                    f"\n\nstop_reason={data['stop_reason']} "
                    f"in={data['usage']['input_tokens']} "
                    f"out={data['usage']['output_tokens']} "
                    f"cost={data['cost']['paise']} paise"
                )
            elif event == "error":
                raise RuntimeError(f"{data['code']}: {data['error']}")

        if not settled:
            raise RuntimeError("stream ended before message_delta")

        print(f"\n{len(''.join(text))} characters received")


    if __name__ == "__main__":
        main()
    ```

=== "Node"

    ```javascript
    // Node 18 or newer, no dependencies. ES modules: save as .mjs, or set
    // "type": "module" in package.json.
    const API = "https://api.tristack.tech";
    const KEY = process.env.TRISTACK_API_KEY;

    export async function* streamMessage(prompt, { model = "nova-micro", signal } = {}) {
      const response = await fetch(`${API}/v1/manifold/messages`, {
        method: "POST",
        signal,
        headers: {
          Authorization: `Bearer ${KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model,
          max_tokens: 1024,
          stream: true,
          messages: [{ role: "user", content: prompt }],
        }),
      });

      if (!response.ok) {
        // A failure before the first event is plain JSON, not SSE.
        const failure = await response.json();
        throw new Error(
          `${response.status} ${failure.code ?? "-"}: ${failure.error ?? failure.title}`,
        );
      }

      const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += value;
        let boundary = buffer.indexOf("\n\n");
        while (boundary !== -1) {
          const frame = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          boundary = buffer.indexOf("\n\n");

          let event = null;
          let data = null;
          for (const line of frame.split("\n")) {
            if (line.startsWith("event: ")) event = line.slice(7);
            else if (line.startsWith("data: ")) data = line.slice(6);
          }
          if (event && data) yield [event, JSON.parse(data)];
        }
      }
    }

    let settled = false;
    for await (const [event, data] of streamMessage("Count to five.")) {
      if (event === "content_block_delta") {
        process.stdout.write(data.delta.text);
      } else if (event === "message_delta") {
        settled = true;
        console.log(
          `\n\nstop_reason=${data.stop_reason}`,
          `in=${data.usage.input_tokens}`,
          `out=${data.usage.output_tokens}`,
          `cost=${data.cost.paise} paise`,
        );
      } else if (event === "error") {
        throw new Error(`${data.code}: ${data.error}`);
      }
    }

    if (!settled) throw new Error("stream ended before message_delta");
    ```

=== "curl"

    ```bash
    curl -N https://api.tristack.tech/v1/manifold/messages \
      -H "Authorization: Bearer $TRISTACK_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "model": "nova-micro",
        "max_tokens": 1024,
        "stream": true,
        "messages": [
          { "role": "user", "content": "Count to five." }
        ]
      }'
    ```

    `-N` disables curl's own buffering. Without it the events arrive in one lump at the
    end, which looks like streaming is broken when it is not.

## Aborting from your code

=== "Python"

    ```python
    # Stop reading once you have enough. Breaking out of the loop closes the response,
    # which aborts the request; the call still settles, for the whole input plus whatever
    # output had already been delivered.
    for event, data in stream_message("Write a long essay about rain."):
        if event == "content_block_delta":
            print(data["delta"]["text"], end="", flush=True)
            if "\n\n" in data["delta"]["text"]:
                break
    ```

=== "Node"

    ```javascript
    // Continues the module above, so the same .mjs (or "type": "module") rule applies.
    const controller = new AbortController();
    setTimeout(() => controller.abort(), 2000);

    try {
      for await (const [event, data] of streamMessage("Write a long essay about rain.", {
        signal: controller.signal,
      })) {
        if (event === "content_block_delta") process.stdout.write(data.delta.text);
      }
    } catch (error) {
      if (error.name !== "AbortError") throw error;
      console.log("\nstopped early; billed for the input plus what arrived");
    }
    ```

## Choosing between streaming and a single response

Stream when a person is watching the output appear. Take the single JSON response when a
program consumes the result: it is simpler, it hands you `usage` and `cost` in the same
object as the text, and there is no partial-failure case to handle. The token price is
identical either way.

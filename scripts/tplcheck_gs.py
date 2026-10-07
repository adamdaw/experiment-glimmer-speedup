"""Render a tool-call history through a model's chat template (/apply-template) and check whether the
assistant's reasoning_content from the tool-call turn reaches the prompt (reasoning preserved between tool steps)."""
import json, sys, os, urllib.request
BASE = os.environ.get("GS_BASE", "http://localhost:8080")
model = sys.argv[1]
R = "REASONING-MARKER-7731: I should call get_weather for Oslo first."
tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}}}]
def render(msgs):
    body = {"messages": msgs, "tools": tools}
    req = urllib.request.Request(f"{BASE}/upstream/{model}/apply-template", json.dumps(body).encode(), {"content-type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req))["prompt"]
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.read().decode()[:300]}"
base = [{"role": "user", "content": "Weather in Oslo?"}]
tc = [{"id": "c1", "type": "function", "function": {"name": "get_weather", "arguments": "{\"city\": \"Oslo\"}"}}]
cases = {
  "reasoning, empty content (mid tool chain)": base + [{"role": "assistant", "content": "", "reasoning_content": R, "tool_calls": tc}, {"role": "tool", "tool_call_id": "c1", "content": "{\"temp_c\": 4}"}],
  "reasoning + non-empty content (mid tool chain)": base + [{"role": "assistant", "content": "Checking.", "reasoning_content": R, "tool_calls": tc}, {"role": "tool", "tool_call_id": "c1", "content": "{\"temp_c\": 4}"}],
  "after a final answer + new user turn": base + [{"role": "assistant", "content": "", "reasoning_content": R, "tool_calls": tc}, {"role": "tool", "tool_call_id": "c1", "content": "{\"temp_c\": 4}"}, {"role": "assistant", "content": "4 C."}, {"role": "user", "content": "And Bergen?"}],
}
for k, msgs in cases.items():
    p = render(msgs)
    print(f"[{k}] reasoning in prompt: {R in p}")
    i = p.find("Weather in Oslo?")
    print("   ", p[i:i + 420].replace("\n", "\\n") if i >= 0 else p[:300])

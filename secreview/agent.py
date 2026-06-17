import anthropic
import datetime
import json
client=anthropic.Anthropic(api_key=process.env["ANTHROPIC_API_KEY"])

tools = [{
    "name": "get_time",
    "description": "Return the current UTC time as an ISO string.",
    "input_schema": {"type": "object", "properties": {}},
}]


def run_tool(name, inp):
    if name == "get_time":
        return {"utc": datetime.datetime.utcnow().isoformat()}
    return {"error": "unknown tool"}

messages= [{"role": "user", "content": "What is the current time?"}]
while True:
    resp= client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        tools=tools,
        messages=messages,
    )

    messages.append({"role": "assistant", "content": resp.content})

    if resp.stop_reason != "tool_use":
        print(resp.content[0].text)
        break

    results = []
    for block in resp.content:
        if block.type == "tool_use":
            out = run_tool(block.name, block.input)
            results.append({"type": "tool_result", "tool_use_id":block.id, "content": json.dumps(out)})


    messages.append({"role": "user", "content": results})
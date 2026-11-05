
from ollama import chat
from app.tools import multiply


def ask_ai(message: str):
    messages = [
        {
            "role": "user",
            "content": message
        }
    ]

    response = chat(
        model="qwen3:1.7b",
        messages=messages,
        tools=[multiply]
    )

    if response.message.tool_calls:
        messages.append(response.message)
        print("🔧 AI TOOL CALL DETECTED!")
        
        for tool in response.message.tool_calls:
            if tool.function.name == "multiply":
                args = tool.function.arguments

                result = multiply(
                    int(args["a"]),
                    int(args["b"])
                )
                print("Result:", result)
                print("Tool:", tool.function.name)
                print("Arguments:", tool.function.arguments)
                messages.append({
                    "role": "tool",
                    "tool_name": "multiply",
                    "content": str(result)
                })

        response = chat(
            model="qwen3:1.7b",
            messages=messages
        )

    return response.message.content

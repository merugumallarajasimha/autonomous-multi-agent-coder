from langgraph.graph import StateGraph, END
from typing import TypedDict
from langchain_ollama import ChatOllama

class State(TypedDict):
    message: str
    reply: str

# Connect to local Ollama model
llm = ChatOllama(model="qwen2.5:3b")

def echo_node(state: State):
    resp = llm.invoke(state["message"])
    return {"reply": resp.content}

# Build simple graph
graph = StateGraph(State)
graph.add_node("echo", echo_node)
graph.set_entry_point("echo")
graph.add_edge("echo", END)

app = graph.compile()

if __name__ == "__main__":
    result = app.invoke({"message": "Say hello and confirm you're working."})
    print("Ollama Response:\n", result["reply"])
import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional
import os
import re

import nest_asyncio
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import httpx

# Allow nested event loops (Jupyter/IPython)
nest_asyncio.apply()

# Load environment variables
load_dotenv("./.env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


class MCPGeminiClient:
    """Client for interacting with Gemini models using MCP tools"""

    def __init__(self, model: str = "gemini-2.0-flash"):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.model = model
        self.stdio: Optional[Any] = None
        self.write: Optional[Any] = None

    async def connect_to_server(self, server_script_path: str = "server.py"):
        """Connect to MCP server via stdio."""
        server_params = StdioServerParameters(command="python", args=[server_script_path])
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()

        tools_result = await self.session.list_tools()
        print("\nConnected to server with tools:")
        for tool in tools_result.tools:
            print(f"  - {tool.name}: {tool.description}")

    async def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """Return tools in the Gemini-style function format."""
        tools_result = await self.session.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
            for tool in tools_result.tools
        ]

    async def gemini_chat(self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Send messages to Gemini and return the assistant response."""
        # Build system + conversation text (OpenAI-style)
        conversation_text = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                conversation_text += f"SYSTEM: {content}\n"
            elif role == "user":
                conversation_text += f"USER: {content}\n"
            elif role == "assistant":
                conversation_text += f"ASSISTANT: {content}\n"
            elif role == "tool":
                conversation_text += f"TOOL ({msg.get('tool_call_id', '')}): {content}\n"

        # Include available tools in the system prompt
        if tools:
            conversation_text += f"AVAILABLE TOOLS: {json.dumps(tools)}\n"

        payload = {
            "contents": [{"parts": [{"text": conversation_text}]}]
        }
        headers = {"Content-Type": "application/json", "X-goog-api-key": GEMINI_API_KEY}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(GEMINI_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Extract text from Gemini
        candidate_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        candidate_text_clean = re.sub(r"^```json\s*|\s*```$", "", candidate_text.strip(), flags=re.MULTILINE)
        return {"content": candidate_text_clean, "raw": data}

    async def process_query(self, query: str) -> str:
        """Process query using Gemini and MCP tools (OpenAI style)."""
        tools = await self.get_mcp_tools()

        # Initial conversation
        messages = [{"role": "user", "content": query}]
        assistant_response = await self.gemini_chat(messages, tools)
        assistant_text = assistant_response["content"]

        # Check for tool calls by looking for known tool names in text
        tool_calls = []
        for tool in tools:
            if tool["function"]["name"] in assistant_text:
                tool_calls.append({
                    "name": tool["function"]["name"],
                    "arguments": {}  # optionally parse arguments if structured
                })

        # If tool calls exist, execute them
        if tool_calls:
            for call in tool_calls:
                result = await self.session.call_tool(call["name"], arguments=call.get("arguments", {}))
                messages.append({"role": "assistant", "content": assistant_text})
                messages.append({"role": "tool", "tool_call_id": call.get("name", ""), "content": result.content[0].text})

            # Final Gemini response after tools
            final_response = await self.gemini_chat(messages, tools)
            return final_response["content"]

        return assistant_text

    async def cleanup(self):
        """Close resources."""
        await self.exit_stack.aclose()


async def main():
    client = MCPGeminiClient()
    try:
        await client.connect_to_server("server.py")

        query = "What is our company's vacation and remote work policy?"
        # query = "What 1 + 5?"
        print(f"\nQuery: {query}")

        response = await client.process_query(query)
        print(f"\nResponse: {response}")
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

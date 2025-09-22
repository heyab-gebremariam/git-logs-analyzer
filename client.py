import asyncio
import json
import logging
import os
import re
from contextlib import AsyncExitStack
from typing import Any, List, Optional, Dict

import nest_asyncio
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import httpx
from models import Report, MergedInput, Commit, JiraIssue


# Load environment
load_dotenv("./.env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

nest_asyncio.apply()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class MCPGeminiClient:
    def __init__(self, model: str = "gemini-2.0-flash"):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.model = model
        self.stdio: Optional[Any] = None
        self.write: Optional[Any] = None

    async def connect_to_server(self, server_script_path: str = "server.py"):
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

    async def gemini_chat(self, messages: List[Dict[str, str]]) -> str:
        conversation_text = ""
        for msg in messages:
            conversation_text += f"{msg['role'].upper()}: {msg['content']}\n"

        payload = {"contents": [{"parts": [{"text": conversation_text}]}]}
        headers = {"Content-Type": "application/json", "X-goog-api-key": GEMINI_API_KEY}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(GEMINI_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        candidate_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return re.sub(r"^```json\s*|\s*```$", "", candidate_text.strip(), flags=re.MULTILINE)

    async def process_query(self, query: str) -> str:
        messages = [{"role": "user", "content": query}]
        return await self.gemini_chat(messages)

    async def safe_json_load(self, text: str) -> Any:
        try:
            return json.loads(text) if text else []
        except json.JSONDecodeError:
            logging.warning(f"Failed to decode JSON: {text[:100]}...")
            return []

    async def cleanup(self):
        await self.exit_stack.aclose()

async def main():
    client = MCPGeminiClient()
    all_reports = []  # collect all reports

    try:
        await client.connect_to_server("server.py")

        # 1) Get all authors
        authors_res = await client.session.call_tool("get_authors", {})
        authors_data = json.loads(authors_res.content[0].text) if authors_res.content else []

        for author in authors_data:
            name = author.get("name", "UNKNOWN")
            email = author.get("emails", [None])[0]
            logging.info(f"Processing author={name}, email={email}")

            # 2) Tickets + commits by email
            tickets_res = await client.session.call_tool(
                "get_tickets_and_commits_by_email", {"email": email}
            )
            tickets_and_commits_data = json.loads(tickets_res.content[0].text) if tickets_res.content else {}

            logging.info(f"Tickets and commits for {name}: {len(tickets_and_commits_data)}")

            # 3) Build MergedInput object
            merged_input = MergedInput(
                email=tickets_and_commits_data.get("email", ""),
                name=tickets_and_commits_data.get("name", ""),
                tickets=[JiraIssue(**t) for t in tickets_and_commits_data.get("tickets", [])],
                regular_commits=[Commit(**c) for c in tickets_and_commits_data.get("regular_commits", [])],
                overtime_commits=[Commit(**c) for c in tickets_and_commits_data.get("overtime_commits", [])],
            )

            # 4) Ask Gemini to summarize
            query = (
                f"Summarize the following commits and tickets for {name} as a concise report:\n"
                f"Tickets: {tickets_and_commits_data.get('tickets', [])}\n"
                f"Regular Commits: {tickets_and_commits_data.get('regular_commits', [])}\n"
                f"Overtime Commits: {tickets_and_commits_data.get('overtime_commits', [])}\n"
                "Format strictly as a report."
            )
            summary = await client.process_query(query)
            logging.info(f"Gemini response snippet: {summary[:200].replace(chr(10), ' ')}...")

            # 5) Build final Report object
            report = Report(
                developer_email=email,
                ai_summary=summary,
                tickets_and_commits=merged_input
            )

            all_reports.append(report)  # collect report
            logging.info(f"Report object created for {name}, added to batch.")

        # 6) Save all reports locally
        save_res = await client.session.call_tool(
            "save_reports_batch",
            {"reports": [r.__dict__ for r in all_reports]}
        )
        logging.info(f"Save batch result: {save_res.content[0].text if save_res.content else save_res}")

        # 7) Send all reports via Slack
        slack_res = await client.session.call_tool(
            "send_reports_batch_slack",
            {"reports": [r.__dict__ for r in all_reports]}
        )
        logging.info(f"Slack send result: {slack_res.content[0].text if slack_res.content else slack_res}")

        # 8) Send all reports via Gmail
        gmail_res = await client.session.call_tool(
            "send_reports_batch_gmail",
            {"reports": [r.__dict__ for r in all_reports]}
        )
        logging.info(f"Gmail send result: {gmail_res.content[0].text if gmail_res.content else gmail_res}")

    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

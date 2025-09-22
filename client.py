import asyncio
import json
import logging
import os
import re
import sys
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

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

class MCPGeminiClient:
    def __init__(self, model: str = "gemini-2.0-flash"):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.model = model
        self.stdio: Optional[Any] = None
        self.write: Optional[Any] = None

    async def connect_to_server(self, server_script_path: str = "server.py"):
        logging.debug(f"Connecting to MCP server at {server_script_path}...")
        server_params = StdioServerParameters(command="python", args=[server_script_path])
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()
        logging.info("Connected to MCP server.")

        tools_result = await self.session.list_tools()
        logging.debug(f"Available tools: {[tool.name for tool in tools_result.tools]}")

            
    async def gemini_chat(self, messages: List[Dict[str, str]]) -> str:
        conversation_text = "".join(f"{msg['role'].upper()}: {msg['content']}\n" for msg in messages)
        payload = {"contents": [{"parts": [{"text": conversation_text}]}]}
        headers = {"Content-Type": "application/json", "X-goog-api-key": GEMINI_API_KEY}

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                resp = await client.post(GEMINI_API_URL, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logging.error(f"Gemini request failed: {e}")
                return f"[ERROR] {e}"

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
        logging.info("Cleanup done.")

async def main():
    client = MCPGeminiClient()
    all_reports = []

    try:
        await client.connect_to_server("server.py")
        authors_res = await client.session.call_tool("get_authors", {})
        authors_data = json.loads(authors_res.content[0].text) if authors_res.content else []
        logging.info(f"Found {len(authors_data)} authors.")

        for author in authors_data:
            name = author.get("name", "UNKNOWN")
            email = author.get("emails", [None])[0]
            logging.info(f"Processing author={name}, email={email}")

            # Tickets + commits
            tickets_res = await client.session.call_tool(
                "get_tickets_and_commits_by_email", {"email": email}
            )
            tickets_and_commits_data = json.loads(tickets_res.content[0].text) if tickets_res.content else {}

            merged_input = MergedInput(
                email=tickets_and_commits_data.get("email", ""),
                name=tickets_and_commits_data.get("name", ""),
                tickets=[JiraIssue(**t) for t in tickets_and_commits_data.get("tickets", [])],
                regular_commits=[Commit(**c) for c in tickets_and_commits_data.get("regular_commits", [])],
                overtime_commits=[Commit(**c) for c in tickets_and_commits_data.get("overtime_commits", [])],
            )

            # Gemini summary
            query = (
                f"Summarize commits and tickets for {name} concisely:\n"
                f"Tickets: {tickets_and_commits_data.get('tickets', [])}\n"
                f"Regular: {tickets_and_commits_data.get('regular_commits', [])}\n"
                f"Overtime: {tickets_and_commits_data.get('overtime_commits', [])}"
            )
            summary = await client.process_query(query)

            report = Report(
                developer_email=email,
                ai_summary=summary,
                tickets_and_commits=merged_input
            )
            all_reports.append(report)

        # Save batch
        save_res = await client.session.call_tool(
            "save_reports_batch",
            {"reports": [r.__dict__ for r in all_reports]}
        )
        logging.info(f"Save batch result: {save_res.content[0].text if save_res.content else save_res}")

        # Gmail
        smtp_data = {
            "SMTP_HOST": os.getenv("SMTP_HOST", "smtp.gmail.com"),
            "SMTP_PORT": int(os.getenv("SMTP_PORT", 587)),
            "SMTP_USERNAME": os.getenv("SMTP_USERNAME"),
            "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD")
        }
        gmail_res = await client.session.call_tool(
            "send_reports_batch_gmail",
            {
                "reports": [r.__dict__ for r in all_reports],
                "recipient": "heyab.gebremariam@gmail.com",
                "subject": "Git Reports",
                "smtp_data": smtp_data
            }
        )
        logging.info(f"Gmail send result: {gmail_res.content[0].text if gmail_res.content else gmail_res}")


    except Exception as e:
        logging.error(f"Fatal error in main: {e}")
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

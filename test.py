import asyncio
import json
import logging
import os
import sys
from contextlib import AsyncExitStack
from typing import Any

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Load environment in test.py
load_dotenv("./.env")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

class MCPTestClient:
    def __init__(self):
        self.session: Any = None
        self.exit_stack = AsyncExitStack()
        self.stdio: Any = None
        self.write: Any = None

    async def connect_to_server(self, server_script_path: str = "server.py"):
        logging.debug(f"Connecting to MCP server at {server_script_path}...")

        # Environment for subprocess is optional here, since we will pass creds directly
        self.stdio, self.write = await self.exit_stack.enter_async_context(
            stdio_client(
                StdioServerParameters(
                    command="python",
                    args=[server_script_path],
                )
            )
        )

        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()
        logging.info("Connected to MCP server.")

    async def cleanup(self):
        await self.exit_stack.aclose()
        logging.info("Cleanup done.")

async def main():
    client = MCPTestClient()
    try:
        await client.connect_to_server("server.py")

        # Load reports.json
        reports_path = os.path.join(os.path.dirname(__file__), "data", "reports.json")
        logging.debug(f"Loading reports from {reports_path}...")
        if not os.path.exists(reports_path):
            logging.error(f"{reports_path} not found!")
            return

        with open(reports_path, "r", encoding="utf-8") as f:
            reports = json.load(f)
        logging.info(f"Loaded {len(reports)} reports.")

        if not reports:
            logging.warning("No reports to send.")
            return

        # Prepare SMTP credentials from .env
        smtp_data = {
            "SMTP_HOST": os.getenv("SMTP_HOST", "smtp.gmail.com"),
            "SMTP_PORT": int(os.getenv("SMTP_PORT", 587)),
            "SMTP_USERNAME": os.getenv("SMTP_USERNAME"),
            "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD")
        }

        # Send via Gmail, passing all credentials as arguments
        logging.info("Sending reports via Gmail...", smtp_data)
        gmail_res = await client.session.call_tool(
            "send_reports_batch_gmail",
            {
                "reports": reports,
                "recipient": "heyab.gebremariam@gmail.com",
                "subject": "Test Reports",
                "smtp_data": smtp_data
            }
        )
        logging.info(f"Gmail result: {gmail_res.content[0].text if gmail_res.content else gmail_res}")

    except Exception as e:
        logging.exception(f"Fatal error: {e}")
    finally:
        await client.cleanup()
        logging.info("MCP test client shutdown complete.")

if __name__ == "__main__":
    logging.info("Starting test.py...")
    asyncio.run(main())
    logging.info("Finished test.py.")

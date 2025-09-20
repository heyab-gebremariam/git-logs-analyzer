# client_call_jira.py (example)
import asyncio
from your_existing_client_file import MCPGeminiClient  # or paste MCPGeminiClient class here

async def run_lookup():
    client = MCPGeminiClient()
    try:
        await client.connect_to_server("server.py")
        # Call the new tool directly via MCP session
        # Note: the underlying session exposes .call_tool(name, arguments={})
        # Your session is available at client.session
        print("Calling get_jira_tickets_for_commits tool...")
        # arguments: commits_path is optional; leave None to use default .env path
        result = await client.session.call_tool("get_jira_tickets_for_commits", arguments={"commits_path": "./data/commits.json", "max_issues_per_user": 20})
        # result.content is a list of text parts - adapt as needed depending on MCP library version
        # many MCP wrappers put the text in result.content[0].text ; else fallback to str(result)
        try:
            text = result.content[0].text
        except Exception:
            text = str(result)
        print("Tool output:\n")
        print(text)
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(run_lookup())

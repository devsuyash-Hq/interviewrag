"""
Smoke test for the InterviewRAG MCP server (no Claude Desktop needed).

It starts mcp_server.py the same way an MCP app would (stdio), asks which
tools exist, and calls the two that only need Ollama embeddings.

Run (Ollama must be running):
  uv run python test_mcp_client.py
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = Path(__file__).parent / "mcp_server.py"


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Tools exposed by the server:")
            for tool in tools.tools:
                print(f"  - {tool.name}")

            print("\n--- list_notes ---")
            result = await session.call_tool("list_notes", {})
            print(result.content[0].text)

            print("\n--- search_notes: 'What is HNSW?' ---")
            result = await session.call_tool(
                "search_notes", {"query": "What is HNSW?", "top_k": 2}
            )
            print(result.content[0].text[:700])


if __name__ == "__main__":
    asyncio.run(main())

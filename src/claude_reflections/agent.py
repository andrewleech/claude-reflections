"""Claude Agent SDK integration for reading and answering from search results."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from .search import SearchResult

if TYPE_CHECKING:
    from claude_code_sdk import ClaudeSDKClient


class ProjectAgent:
    """Manages persistent Claude Code agents per project.

    Each project gets its own agent instance that can be reused for follow-up
    questions. After each answer, we aim to compact the context to keep the
    agent responsive for subsequent queries.
    """

    _clients: dict[str, ClaudeSDKClient] = {}

    @classmethod
    def _get_project_cwd(cls, project: str) -> Path:
        """Get the working directory for a project."""
        projects_dir = Path(os.path.expanduser("~/.claude/projects"))
        return projects_dir / project

    @classmethod
    async def get_or_create(cls, project: str) -> ClaudeSDKClient:
        """Get or create a persistent agent for a project."""
        # Import here to avoid import errors if SDK not installed
        from claude_code_sdk import ClaudeAgentOptions, ClaudeSDKClient

        if project not in cls._clients:
            cwd = cls._get_project_cwd(project)

            options = ClaudeAgentOptions(
                allowed_tools=["Read"],  # Read-only access
                cwd=str(cwd),
                max_turns=10,
                system_prompt=(
                    "You are a helpful assistant that reads JSONL conversation files "
                    "to answer questions about past conversations. "
                    "When given file paths and line numbers, read the surrounding context "
                    "to understand the full conversation and provide accurate answers."
                ),
            )

            client = ClaudeSDKClient(options=options)
            cls._clients[project] = client

        return cls._clients[project]

    @classmethod
    async def close(cls, project: str) -> None:
        """Close an agent for a project."""
        if project in cls._clients:
            client = cls._clients.pop(project)
            # SDK should handle cleanup when context exits
            await client.__aexit__(None, None, None)

    @classmethod
    async def close_all(cls) -> None:
        """Close all active agents."""
        for project in list(cls._clients.keys()):
            await cls.close(project)

    @classmethod
    def format_search_results(cls, results: list[SearchResult]) -> str:
        """Format search results for the agent prompt."""
        if not results:
            return "No search results found."

        lines = ["Search Results:"]
        for i, r in enumerate(results, 1):
            lines.append(f"\n{i}. [{r.role}] Score: {r.score:.3f}")
            lines.append(f"   File: {r.file_path}")
            lines.append(f"   Line: {r.line_number}")
            lines.append(f"   Time: {r.timestamp}")
            lines.append(f"   Preview: {r.snippet[:200]}...")

        return "\n".join(lines)

    @classmethod
    async def answer(
        cls,
        project: str,
        query: str,
        results: list[SearchResult],
        context_lines: int = 50,
    ) -> str:
        """Use an agent to answer a question based on search results.

        Args:
            project: The project name
            query: The user's question
            results: Search results pointing to relevant file locations
            context_lines: Number of lines around each match to read

        Returns:
            The agent's answer
        """
        from claude_code_sdk import query as sdk_query

        formatted_results = cls.format_search_results(results)

        prompt = f"""The user asked: "{query}"

{formatted_results}

Please read the JSONL files at the specified line numbers (reading about
{context_lines} lines around each match) to understand the full context of
these conversations. Then provide a clear, helpful answer to the user's
question based on what you find.

Focus on extracting the relevant information from the conversation history.
Include specific details, code snippets, or solutions that were discussed."""

        # Get project cwd for the query options
        from claude_code_sdk import ClaudeAgentOptions

        cwd = cls._get_project_cwd(project)
        options = ClaudeAgentOptions(
            allowed_tools=["Read"],
            cwd=str(cwd),
            max_turns=5,
        )

        # Collect response
        response_parts: list[str] = []
        async for message in sdk_query(prompt=prompt, options=options):
            # Messages may be text or other types
            if hasattr(message, "content"):
                response_parts.append(str(message.content))
            elif hasattr(message, "text"):
                response_parts.append(str(message.text))
            else:
                response_parts.append(str(message))

        return "\n".join(response_parts)


async def simple_answer(
    query: str,
    results: list[SearchResult],
    project: str,
) -> str:
    """Simple wrapper to answer a question using search results.

    This is a convenience function that doesn't maintain persistent state.
    """
    return await ProjectAgent.answer(
        project=project,
        query=query,
        results=results,
    )

"""FastMCP server providing reflection tools."""

from __future__ import annotations

import logging
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .agent import ProjectAgent
from .indexer import (
    discover_jsonl_files,
    get_final_offset,
    get_project_path,
    iter_new_messages,
    list_all_projects,
)
from .search import QdrantManager, SearchResult
from .state import StateManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP(
    name="claude-reflections",
    instructions=(
        "Reflection tools for searching past conversations. "
        "Use 'search' to find relevant past discussions, "
        "and 'answer' to get detailed responses from conversation context."
    ),
)

# Managers (lazily initialized)
_state_manager: StateManager | None = None
_qdrant_managers: dict[str, QdrantManager] = {}


def get_state_manager() -> StateManager:
    """Get or create the state manager."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def get_qdrant_manager(project: str) -> QdrantManager:
    """Get or create a Qdrant manager for a project."""
    if project not in _qdrant_managers:
        state = get_state_manager().load(project)
        _qdrant_managers[project] = QdrantManager(state.collection_name)
    return _qdrant_managers[project]


@mcp.tool()
async def search(
    query: Annotated[str, Field(description="Search query for past conversations")],
    project: Annotated[
        str | None,
        Field(description="Project name to search (default: all projects)"),
    ] = None,
    limit: Annotated[int, Field(description="Maximum number of results", ge=1, le=50)] = 5,
) -> str:
    """Search past conversations for relevant discussions.

    Returns file paths and line numbers that can be used to read original context.
    """
    results: list[SearchResult] = []

    projects = [project] if project else list_all_projects()

    for proj in projects:
        qdrant = get_qdrant_manager(proj)
        proj_results = qdrant.search(query, limit=limit)

        # Add project info to results
        for r in proj_results:
            results.append(r)

    # Sort by score and limit
    results.sort(key=lambda r: r.score, reverse=True)
    results = results[:limit]

    if not results:
        return "No matching conversations found."

    # Format results
    lines = [f"Found {len(results)} relevant conversation(s):\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. [{r.role}] Score: {r.score:.3f}")
        lines.append(f"   File: {r.file_path}")
        lines.append(f"   Line: {r.line_number}")
        lines.append(f"   Time: {r.timestamp}")
        lines.append(f"   Preview: {r.snippet}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def answer(
    query: Annotated[str, Field(description="Question to answer based on past conversations")],
    project: Annotated[
        str | None,
        Field(description="Project name to search (required for answer)"),
    ] = None,
    limit: Annotated[int, Field(description="Number of search results to use")] = 5,
) -> str:
    """Search and answer a question using past conversation context.

    This tool searches for relevant conversations and uses an AI agent to read
    the original JSONL files and provide a detailed answer.
    """
    if not project:
        # Try to determine project from context or use first available
        projects = list_all_projects()
        if not projects:
            return "No projects found. Please index some conversations first."
        project = projects[0]

    # First, search for relevant results
    qdrant = get_qdrant_manager(project)
    results = qdrant.search(query, limit=limit)

    if not results:
        return f"No relevant conversations found in project '{project}'."

    # Use agent to read and answer
    try:
        response = await ProjectAgent.answer(
            project=project,
            query=query,
            results=results,
        )
        return response
    except ImportError:
        # SDK not installed, return search results instead
        return "Agent SDK not available. Search results:\n\n" + ProjectAgent.format_search_results(
            results
        )
    except Exception as e:
        logger.exception("Error in answer tool")
        return f"Error generating answer: {e}\n\nSearch results found: {len(results)}"


@mcp.tool()
async def index_status(
    project: Annotated[
        str | None,
        Field(description="Project name (default: all projects)"),
    ] = None,
) -> str:
    """Get indexing status for project(s)."""
    state_mgr = get_state_manager()

    projects = [project] if project else state_mgr.list_projects()

    if not projects:
        return "No projects indexed yet."

    lines = ["Indexing Status:\n"]
    for proj in projects:
        stats = state_mgr.get_stats(proj)
        qdrant = get_qdrant_manager(proj)
        qdrant_stats = qdrant.get_collection_stats()

        lines.append(f"Project: {proj}")
        lines.append(f"  Collection: {stats['collection_name']}")
        lines.append(f"  Files tracked: {stats['files_tracked']}")
        lines.append(f"  Total indexed: {stats['total_indexed']}")
        lines.append(f"  Qdrant points: {qdrant_stats['points_count']}")
        lines.append(f"  Qdrant status: {qdrant_stats['status']}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def reindex(
    project: Annotated[str, Field(description="Project name to reindex")],
    full: Annotated[
        bool,
        Field(description="If true, reindex from scratch (default: incremental)"),
    ] = False,
) -> str:
    """Reindex a project's conversations.

    By default, only indexes new content since last run (incremental).
    Use full=true to reindex everything from scratch.
    """
    state_mgr = get_state_manager()

    project_path = get_project_path(project)
    if not project_path.exists():
        return f"Project directory not found: {project_path}"

    jsonl_files = discover_jsonl_files(project_path)
    if not jsonl_files:
        return f"No JSONL files found in {project_path}"

    qdrant = get_qdrant_manager(project)
    total_indexed = 0

    for jsonl_file in jsonl_files:
        filename = jsonl_file.name

        # Get starting offset (0 if full reindex)
        start_offset = 0 if full else state_mgr.get_file_offset(project, filename)

        # Collect new messages
        messages = list(iter_new_messages(jsonl_file, start_offset))

        if messages:
            # Index to Qdrant
            count = qdrant.index_messages(messages)
            total_indexed += count

            # Update state
            final_offset = get_final_offset(jsonl_file)
            state_mgr.update_file_state(project, filename, final_offset, count)

            logger.info(f"Indexed {count} messages from {filename}")

    return (
        f"Indexed {total_indexed} new message(s) from {len(jsonl_files)} file(s) "
        f"in project '{project}'."
    )


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()

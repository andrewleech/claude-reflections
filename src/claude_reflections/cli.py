"""CLI commands for claude-reflections."""

from __future__ import annotations

import argparse
import sys

import httpx
from qdrant_client.http.exceptions import ResponseHandlingException

from .config import get_qdrant_url
from .indexer import (
    discover_jsonl_files,
    get_final_offset,
    get_project_path,
    iter_new_messages,
    list_all_projects,
)
from .search import QdrantManager
from .state import StateManager


def cmd_index(args: argparse.Namespace) -> int:
    """Index conversations for a project."""
    state_mgr = StateManager()

    projects = [args.project] if args.project else list_all_projects()

    if not projects:
        print("No projects found to index.")
        return 0

    total_indexed = 0

    for project in projects:
        state = state_mgr.load(project)
        project_path = get_project_path(project)

        if not project_path.exists():
            print(f"Project directory not found: {project_path}")
            continue

        jsonl_files = discover_jsonl_files(project_path)
        if not jsonl_files:
            continue

        qdrant = QdrantManager(state.collection_name)
        project_indexed = 0

        for jsonl_file in jsonl_files:
            filename = jsonl_file.name

            # Get starting offset (0 if full reindex)
            start_offset = 0 if args.full else state_mgr.get_file_offset(project, filename)

            # Collect new messages
            messages = list(iter_new_messages(jsonl_file, start_offset))

            if messages:
                # Index to Qdrant
                count = qdrant.index_messages(messages)
                project_indexed += count
                total_indexed += count

                # Update state
                final_offset = get_final_offset(jsonl_file)
                state_mgr.update_file_state(project, filename, final_offset, count)

                if args.verbose:
                    print(f"  Indexed {count} messages from {filename}")

        if project_indexed > 0:
            print(f"Indexed {project_indexed} messages in {project}")

    print(f"\nTotal indexed: {total_indexed} messages")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search indexed conversations."""
    state_mgr = StateManager()

    # Auto-index before search only when a specific project is provided
    # Indexing all projects on every search is too slow
    if args.project:
        project_path = get_project_path(args.project)
        if project_path.exists():
            jsonl_files = discover_jsonl_files(project_path)
            if jsonl_files:
                try:
                    state = state_mgr.load(args.project)
                    qdrant = QdrantManager(state.collection_name)

                    # Run incremental indexing silently
                    for jsonl_file in jsonl_files:
                        filename = jsonl_file.name
                        start_offset = state_mgr.get_file_offset(args.project, filename)
                        messages = list(iter_new_messages(jsonl_file, start_offset))

                        if messages:
                            qdrant.index_messages(messages)
                            final_offset = get_final_offset(jsonl_file)
                            state_mgr.update_file_state(
                                args.project, filename, final_offset, len(messages)
                            )
                except Exception as e:
                    print(f"Warning: Auto-indexing failed for {args.project}: {e}")
                    print("Proceeding with search using existing index...")

    # Now perform the search
    projects = [args.project] if args.project else state_mgr.list_projects()

    if not projects:
        print("No projects indexed. Run 'claude-reflections index' first.")
        return 1

    all_results = []

    try:
        for project in projects:
            state = state_mgr.load(project)
            qdrant = QdrantManager(state.collection_name)
            results = qdrant.search(args.query, limit=args.limit)

            for r in results:
                all_results.append((project, r))
    except (httpx.ConnectError, ResponseHandlingException, ConnectionError, OSError) as e:
        qdrant_url = get_qdrant_url()
        print(f"Error: Could not connect to Qdrant at {qdrant_url}. "
              "Is the Qdrant container running?")
        print(f"  Detail: {e}")
        return 1

    # Sort by score
    all_results.sort(key=lambda x: x[1].score, reverse=True)
    all_results = all_results[: args.limit]

    if not all_results:
        print("No results found.")
        return 0

    print(f"Found {len(all_results)} result(s):\n")
    for i, (project, r) in enumerate(all_results, 1):
        print(f"{i}. [{r.role}] Score: {r.score:.3f}")
        print(f"   Project: {project}")
        print(f"   File: {r.file_path}")
        print(f"   Line: {r.line_number}")
        print(f"   Time: {r.timestamp}")
        print(f"   Preview: {r.snippet[:200]}...")
        print()

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show indexing status."""
    state_mgr = StateManager()

    projects = [args.project] if args.project else state_mgr.list_projects()

    if not projects:
        print("No projects indexed yet.")
        return 0

    print("Indexing Status:\n")
    for project in projects:
        stats = state_mgr.get_stats(project)
        state = state_mgr.load(project)
        qdrant = QdrantManager(state.collection_name)
        qdrant_stats = qdrant.get_collection_stats()

        # Get project directory info
        project_path = get_project_path(project)
        jsonl_files = discover_jsonl_files(project_path) if project_path.exists() else []

        print(f"Project: {project}")
        print(f"  Directory: {project_path}")
        print(f"  JSONL files: {len(jsonl_files)}")
        print(f"  Collection: {stats['collection_name']}")
        print(f"  Files tracked: {stats['files_tracked']}")
        print(f"  Total indexed: {stats['total_indexed']}")
        print(f"  Qdrant points: {qdrant_stats['points_count']}")
        print(f"  Qdrant status: {qdrant_stats['status']}")
        print()

    return 0


def cmd_list_projects(_args: argparse.Namespace) -> int:
    """List available projects."""
    projects = list_all_projects()

    if not projects:
        print("No projects found in ~/.claude/projects/")
        return 0

    print("Available projects:\n")
    for project in projects:
        project_path = get_project_path(project)
        jsonl_count = len(list(project_path.glob("*.jsonl")))
        print(f"  {project} ({jsonl_count} files)")

    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="claude-reflections",
        description="Minimal conversation memory with vector search",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Index command
    index_parser = subparsers.add_parser("index", help="Index conversations")
    index_parser.add_argument("--project", "-p", help="Project to index (default: all)")
    index_parser.add_argument(
        "--full", "-f", action="store_true", help="Full reindex (not incremental)"
    )
    index_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    index_parser.set_defaults(func=cmd_index)

    # Search command
    search_parser = subparsers.add_parser("search", help="Search conversations")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--project", "-p", help="Project to search (default: all)")
    search_parser.add_argument("--limit", "-l", type=int, default=5, help="Number of results")
    search_parser.set_defaults(func=cmd_search)

    # Status command
    status_parser = subparsers.add_parser("status", help="Show indexing status")
    status_parser.add_argument("--project", "-p", help="Project to check")
    status_parser.set_defaults(func=cmd_status)

    # List command
    list_parser = subparsers.add_parser("list", help="List available projects")
    list_parser.set_defaults(func=cmd_list_projects)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

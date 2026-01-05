# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Command dispatch for CLI entrypoint."""

from __future__ import annotations

from pathlib import Path

from rich.markup import escape

from motus import __version__
from motus.cli.exit_codes import EXIT_ERROR, EXIT_USAGE
from motus.cli.help import format_cli_resource_id, print_parser_help
from motus.core.errors import DatabaseError, MigrationError
from motus.observability.activity import ActivityLedger


def dispatch_command(
    args,
    *,
    bundle,
    console,
    error_console,
    logger,
    list_sessions,
    watch_command,
    summary_command,
    teleport_command,
) -> None:
    """Dispatch CLI commands based on parsed arguments.

    Args:
        args: Parsed argparse namespace with the command and flags.
        bundle: ParserBundle carrying root and subcommand parsers.
        console: Rich console for standard output.
        error_console: Rich console for error output.
        logger: Logger for debug and error messages.
        list_sessions: Callable for listing sessions.
        watch_command: Callable for watch command handling.
        summary_command: Callable for summary command handling.
        teleport_command: Callable for teleport command handling.

    Raises:
        SystemExit: For commands that exit with explicit status codes.
    """
    command = args.command

    # Bootstrap database on first run (Phase 0 Foundation)
    bootstrap_ok = True
    try:
        from motus.core.bootstrap import ensure_database

        ensure_database()
    except (DatabaseError, MigrationError) as e:
        bootstrap_ok = False
        logger.debug(f"Database bootstrap skipped: {e}")

    # Install shutdown hooks (best-effort)
    try:
        from motus.core.database import get_db_manager
        from motus.core.shutdown import ShutdownManager

        shutdown = ShutdownManager()
        shutdown.register("db_checkpoint_and_close", get_db_manager().checkpoint_and_close)
        shutdown.install_signal_handlers()
    except (DatabaseError, ImportError, OSError, RuntimeError) as e:
        logger.debug(f"Shutdown manager skipped: {e}")

    # Best-effort CLI invocation audit event for tier gating.
    if bootstrap_ok:
        try:
            import sqlite3

            from motus.observability.audit import AuditEvent, AuditLogger

            AuditLogger().emit(
                AuditEvent(
                    event_type="cli",
                    actor="user",
                    action="invoke",
                    resource_type="command",
                    resource_id=format_cli_resource_id(command, args),
                    context={"version": __version__},
                )
            )
        except (DatabaseError, ImportError, TypeError, ValueError, sqlite3.OperationalError):
            pass
        try:
            ActivityLedger().emit(
                actor="user",
                category="cli",
                action="invoke",
                subject={
                    "command": command,
                    "resource_id": format_cli_resource_id(command, args),
                    "cwd": str(Path.cwd()),
                    "version": __version__,
                },
            )
        except Exception:
            pass

    if command == "harness":
        from motus.commands.harness_cmd import harness_command

        harness_command(save=getattr(args, "save", False))
        return
    if command == "context":
        from motus.commands.context_cmd import context_command

        context_command(session_id=getattr(args, "session_id", None))
        return
    if command == "orient":
        from motus.commands.orient_cmd import orient_command

        raise SystemExit(orient_command(args))
    if command == "standards":
        from motus.commands.standards_cmd import (
            standards_list_proposals_command,
            standards_promote_command,
            standards_propose_command,
            standards_reject_command,
            standards_validate_command,
        )

        standards_cmd = getattr(args, "standards_command", None)
        if standards_cmd == "validate":
            raise SystemExit(standards_validate_command(args))
        if standards_cmd == "propose":
            raise SystemExit(standards_propose_command(args))
        if standards_cmd == "list-proposals":
            raise SystemExit(standards_list_proposals_command(args))
        if standards_cmd == "promote":
            raise SystemExit(standards_promote_command(args))
        if standards_cmd == "reject":
            raise SystemExit(standards_reject_command(args))
        print_parser_help(console, bundle.standards_parser)
        raise SystemExit(EXIT_USAGE)
    if command == "activity":
        from motus.commands.activity_cmd import activity_list_command, activity_status_command

        activity_cmd = getattr(args, "activity_command", None)
        if activity_cmd == "list":
            raise SystemExit(activity_list_command(args))
        if activity_cmd == "status":
            raise SystemExit(activity_status_command(args))
        print_parser_help(console, bundle.activity_parser)
        raise SystemExit(EXIT_USAGE)
    if command == "audit":
        from motus.commands.audit_cmd import (
            audit_add_command,
            audit_list_command,
            audit_promote_command,
        )

        audit_cmd = getattr(args, "audit_command", None)
        if audit_cmd == "add":
            raise SystemExit(audit_add_command(args))
        if audit_cmd == "promote":
            raise SystemExit(audit_promote_command(args))
        if audit_cmd == "list":
            raise SystemExit(audit_list_command(args))
        print_parser_help(console, bundle.audit_parser)
        raise SystemExit(EXIT_USAGE)
    if command == "db":
        from motus.commands.db_cmd import (
            db_analyze_command,
            db_checkpoint_command,
            db_stats_command,
            db_vacuum_command,
        )

        db_cmd = getattr(args, "db_command", None)
        if db_cmd == "vacuum":
            raise SystemExit(db_vacuum_command(args))
        if db_cmd == "analyze":
            raise SystemExit(db_analyze_command(args))
        if db_cmd == "stats":
            raise SystemExit(db_stats_command(args))
        if db_cmd == "checkpoint":
            raise SystemExit(db_checkpoint_command(args))

        print_parser_help(console, bundle.db_parser)
        raise SystemExit(EXIT_USAGE)
    if command == "claims":
        from motus.commands.claims_cmd import claims_acquire_command, claims_list_command

        claims_cmd = getattr(args, "claims_command", None)
        if claims_cmd == "acquire":
            raise SystemExit(claims_acquire_command(args))
        if claims_cmd == "list":
            raise SystemExit(claims_list_command(args))
        print_parser_help(console, bundle.claims_parser)
        raise SystemExit(EXIT_USAGE)
    if command == "history":
        from motus.commands.history_cmd import history_command

        history_command()
        return
    if command == "checkpoint":
        from motus.checkpoint import create_checkpoint

        try:
            checkpoint = create_checkpoint(args.label, Path.cwd())
        except ValueError as e:
            error_console.print(f"[red]{escape(str(e))}[/red]")
            raise SystemExit(EXIT_USAGE) from e
        except RuntimeError as e:
            error_console.print(f"[red]{escape(str(e))}[/red]")
            raise SystemExit(EXIT_ERROR) from e

        console.print(f"Checkpoint created: {escape(checkpoint.id)}", markup=False)
        return
    if command == "checkpoints":
        from motus.checkpoint import list_checkpoints

        try:
            checkpoints = list_checkpoints(Path.cwd())
        except ValueError as e:
            error_console.print(f"[red]{escape(str(e))}[/red]")
            raise SystemExit(EXIT_USAGE) from e
        except RuntimeError as e:
            error_console.print(f"[red]{escape(str(e))}[/red]")
            raise SystemExit(EXIT_ERROR) from e

        if not checkpoints:
            console.print("No checkpoints found", markup=False)
            return

        for checkpoint in checkpoints:
            console.print(
                f"{checkpoint.id}\t{checkpoint.label}\t{checkpoint.timestamp}",
                markup=False,
            )
        return
    if command == "rollback":
        from motus.checkpoint import rollback_checkpoint

        try:
            checkpoint = rollback_checkpoint(args.checkpoint_id, Path.cwd())
        except ValueError as e:
            error_console.print(f"[red]{escape(str(e))}[/red]")
            raise SystemExit(EXIT_USAGE) from e
        except RuntimeError as e:
            error_console.print(f"[red]{escape(str(e))}[/red]")
            raise SystemExit(EXIT_ERROR) from e

        console.print(
            f"Rolled back to checkpoint: {escape(checkpoint.id)}",
            markup=False,
        )
        return
    if command == "diff":
        from motus.checkpoint import diff_checkpoint

        try:
            diff = diff_checkpoint(args.checkpoint_id, Path.cwd())
        except ValueError as e:
            error_console.print(f"[red]{escape(str(e))}[/red]")
            raise SystemExit(EXIT_USAGE) from e
        except RuntimeError as e:
            error_console.print(f"[red]{escape(str(e))}[/red]")
            raise SystemExit(EXIT_ERROR) from e

        console.print(diff, end="" if diff.endswith("\n") else "\n", markup=False)
        return
    if command == "watch":
        watch_command(args)
        return
    if command in ("list", "ls"):
        list_sessions(args)
        return
    if command == "sync":
        from motus.commands.sync_cmd import sync_command

        raise SystemExit(sync_command(args))
    if command == "show":
        from motus.commands.show_cmd import show_session

        show_session(args.session_id)
        return
    if command == "feed":
        from motus.commands.feed_cmd import feed_session

        feed_session(args.session_id, tail_lines=getattr(args, "tail_lines", 200))
        return
    if command == "web":
        from motus.ui.web import run_web

        run_web()
        return
    if command == "summary":
        summary_command(args.session_id)
        return
    if command == "teleport":
        teleport_command(args)
        return
    if command == "explain":
        from motus.commands.explain_cmd import explain_command

        raise SystemExit(explain_command(args))
    if command == "doctor":
        from motus.commands.doctor_cmd import doctor_command

        raise SystemExit(
            doctor_command(
                json_output=getattr(args, "json", False),
                fix=getattr(args, "fix", False),
            )
        )
    if command == "errors":
        from motus.commands.errors_cmd import errors_command

        raise SystemExit(errors_command(args))
    if command == "mcp":
        try:
            from motus.mcp import run_server
        except ImportError:
            error_console.print(
                "MCP not installed. Run: pip install -e '.[mcp]'",
                style="red",
                markup=False,
            )
            raise SystemExit(EXIT_ERROR)
        run_server()
        return
    if command == "init":
        from motus.commands.init_cmd import init_command

        init_command(args)
        return
    if command == "install":
        from motus.commands.install_cmd import install_command

        install_command(args)
        return
    if command == "config":
        from motus.commands.config_cmd import config_command

        config_command(getattr(args, "config_args", []))
        return
    if command == "claude":
        from motus.commands.claude_cmd import claude_command

        raise SystemExit(claude_command(args))
    if command == "policy":
        from motus.commands.policy_cmd import (
            policy_plan_command,
            policy_prune_command,
            policy_run_command,
            policy_verify_command,
        )
        from motus.exceptions import ConfigError

        policy_cmd = getattr(args, "policy_command", None)
        try:
            if policy_cmd == "plan":
                policy_plan_command(args)
                return
            if policy_cmd == "prune":
                raise SystemExit(policy_prune_command(args))
            if policy_cmd == "run":
                raise SystemExit(policy_run_command(args))
            if policy_cmd == "verify":
                raise SystemExit(policy_verify_command(args))
        except ConfigError as e:
            error_console.print(f"[red]{escape(str(e))}[/red]")
            raise SystemExit(EXIT_USAGE) from e

        print_parser_help(console, bundle.policy_parser)
        raise SystemExit(EXIT_USAGE)
    if command == "health":
        from motus.commands.health_cmd import (
            health_capture_command,
            health_compare_command,
            health_history_command,
        )

        health_cmd = getattr(args, "health_command", None)
        if health_cmd == "capture":
            raise SystemExit(health_capture_command(args))
        if health_cmd == "compare":
            raise SystemExit(health_compare_command(args))
        if health_cmd == "history":
            raise SystemExit(health_history_command(args))

        print_parser_help(console, bundle.health_parser)
        raise SystemExit(EXIT_USAGE)
    if command == "verify":
        from motus.commands.verify_cmd import verify_clean_command

        verify_cmd = getattr(args, "verify_command", None)
        if verify_cmd == "clean":
            raise SystemExit(verify_clean_command(args))

        print_parser_help(console, bundle.verify_parser)
        raise SystemExit(EXIT_USAGE)
    if command == "handoffs":
        from motus.commands.handoffs_cmd import (
            handoffs_archive_command,
            handoffs_check_command,
            handoffs_list_command,
        )

        handoffs_cmd = getattr(args, "handoffs_command", None)
        if handoffs_cmd == "list":
            raise SystemExit(handoffs_list_command(args))
        if handoffs_cmd == "check":
            raise SystemExit(handoffs_check_command(args))
        if handoffs_cmd == "archive":
            raise SystemExit(handoffs_archive_command(args))

        print_parser_help(console, bundle.handoffs_parser)
        raise SystemExit(EXIT_USAGE)
    if command == "roadmap":
        from motus.commands.roadmap_cmd import handle_roadmap_command

        raise SystemExit(handle_roadmap_command(args))

    if command == "work":
        from motus.commands.work_cmd import handle_work_command

        raise SystemExit(handle_work_command(args))

    if command == "review":
        from motus.commands.review_cmd import review_command

        raise SystemExit(review_command(args))
    if command == "release":
        from motus.commands.release_cmd import release_bundle_command, release_check_command

        release_cmd = getattr(args, "release_command", None)
        if release_cmd == "check":
            raise SystemExit(release_check_command(args))
        if release_cmd == "bundle":
            raise SystemExit(release_bundle_command(args))

        print_parser_help(console, bundle.release_parser)
        raise SystemExit(EXIT_USAGE)

    if command is None:
        console.print("[bold]Motus - Observability for AI agents[/bold]\n")
        console.print("Start the dashboard:")
        console.print(
            "  motus web     Launch web dashboard at http://127.0.0.1:4000\n",
            markup=False,
        )
        console.print("Commands:")
        console.print("  motus list    List all sessions", markup=False)
        console.print("  motus show <id>  Show session details", markup=False)
        console.print("  motus feed <id>  Show recent event feed", markup=False)
        console.print("  motus --help  Full command reference\n", markup=False)
        print_parser_help(console, bundle.parser)
        return

    print_parser_help(console, bundle.parser)
    raise SystemExit(EXIT_USAGE)

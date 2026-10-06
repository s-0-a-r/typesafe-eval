#!/usr/bin/env python3
"""Branch Policy Validator for typesafe-eval.

Enforces release branch workflow contracts:
1. Direct PRs to 'main' from feature/development branches are rejected.
   Only release branches ('release/**') may target 'main'.
2. Development branches must target an active release branch ('release/**').
"""

from __future__ import annotations

import argparse
import os
import re
import sys


def validate_branch_policy(base_ref: str, head_ref: str) -> tuple[bool, str]:
    """Validates whether a PR's base and head branch comply with repository policy.

    Args:
        base_ref: Target branch name (e.g. 'main', 'release/v0.8.0').
        head_ref: Source branch name (e.g. 'feat/foo', 'release/v0.8.0').

    Returns:
        (is_valid, message)
    """
    clean_base = base_ref.strip().replace("refs/heads/", "")
    clean_head = head_ref.strip().replace("refs/heads/", "")

    is_release_branch = bool(re.match(r"^(release/.*|release-please--.*)$", clean_head))

    if clean_base == "main":
        if is_release_branch:
            return True, f"✅ Valid release promotion: '{clean_head}' -> '{clean_base}'."
        return (
            False,
            f"❌ Branch Policy Violation:\n"
            f"Direct pull requests to '{clean_base}' from '{clean_head}' are forbidden.\n"
            f"All development and feature branches must target an active release branch (e.g. 'release/v0.8.0').\n"
            f"Only release branches ('release/*' or 'release-please--*') are permitted to target '{clean_base}'.",
        )

    if clean_base.startswith("release/"):
        if clean_head == "main":
            return (
                False,
                f"❌ Branch Policy Violation:\n"
                f"Cannot merge '{clean_head}' into release branch '{clean_base}'.",
            )
        return True, f"✅ Valid development pull request: '{clean_head}' -> '{clean_base}'."

    return True, f"ℹ️ Custom branch target: '{clean_head}' -> '{clean_base}'."


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PR branch policy.")
    parser.add_argument(
        "--base",
        default=os.environ.get("GITHUB_BASE_REF", ""),
        help="PR target/base branch (defaults to $GITHUB_BASE_REF)",
    )
    parser.add_argument(
        "--head",
        default=os.environ.get("GITHUB_HEAD_REF", ""),
        help="PR source/head branch (defaults to $GITHUB_HEAD_REF)",
    )

    args = parser.parse_args()

    if not args.base or not args.head:
        print("Notice: Missing base or head branch argument. Skipping branch policy check.")
        return 0

    valid, message = validate_branch_policy(args.base, args.head)
    print(message)
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())

"""Pre-commit hook entrypoint for typesafe-eval.

Executes typesafe-eval and translates exit code 3 (runtime error / missing TYPESAFE_API_KEY)
to exit code 0, allowing CI / untrusted fork runs (e.g. pre-commit.ci) to pass gracefully
without blocking commits.
"""

import sys
from typesafe_eval.cli import main


def pre_commit_main() -> None:
    try:
        main()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        if code == 3:
            sys.stderr.write(
                "typesafe-eval: skipped execution due to missing secret or runtime unavailable (exit code 3).\n"
            )
            sys.exit(0)
        sys.exit(code)


if __name__ == "__main__":
    pre_commit_main()

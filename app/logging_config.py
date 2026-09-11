import logging
import sys


def configure_logging(level: int = logging.INFO) -> None:
    """Send structured-ish logs to stdout so the host platform captures them.

    The assessment requires collected patient payloads to be observable; writing
    to stdout means Render, Docker and a local terminal all pick them up without
    extra wiring.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s | %(message)s")
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

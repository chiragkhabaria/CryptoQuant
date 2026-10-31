"""Standalone job worker: ``python -m cryptoquantui.worker``.

Use this instead of the in-process thread when the web process can be
restarted or scaled (e.g. Azure App Service).
"""

import logging

from cryptoquantui.jobs import worker_loop

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    worker_loop()

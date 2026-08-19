"""Public CLI assembly facade."""

from .app import app
from .commands import register_root
from .commands.diff import diff
from .commands.diff import register as register_diff
from .commands.download import (
    cleanup_command,
    download_command,
    register_cleanup,
)
from .commands.download import (
    register as register_download,
)
from .commands.list import list_versions
from .commands.list import register as register_list
from .commands.query import query
from .commands.query import register as register_query
from .commands.root import main
from .commands.show import register as register_show
from .commands.show import show

register_root(app, main)
register_list(app, list_versions)
register_download(app, download_command)
register_cleanup(app, cleanup_command)
register_query(app, query)
register_diff(app, diff)
register_show(app, show)

__all__ = ["app"]

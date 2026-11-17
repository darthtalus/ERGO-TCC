"""Database-driver compatibility.

PyMySQL is required for the normal MySQL/MariaDB deployment.  The guarded
import lets the isolated SQLite test settings start even when that optional
driver is not installed in a minimal CI image.
"""
try:
    import pymysql
except ImportError:  # pragma: no cover - only used by minimal SQLite CI
    pymysql = None
else:
    pymysql.install_as_MySQLdb()

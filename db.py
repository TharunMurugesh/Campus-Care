import os
import time
import threading
from functools import wraps

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

load_dotenv()

_pool = None
_pool_lock = threading.Lock()

_CACHE_TTL = 60
_cache = {}
_cache_lock = threading.Lock()


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            _pool = ThreadedConnectionPool(
                minconn=int(os.getenv("DB_POOL_MIN", "2")),
                maxconn=int(os.getenv("DB_POOL_MAX", "10")),
                host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", "5432"),
                dbname=os.getenv("DB_NAME", "campus_issue_system"),
                user=os.getenv("DB_USER", "campus_app"),
                password=os.getenv("DB_PASSWORD", "postgres"),
            )
    return _pool


def _get_conn():
    return _get_pool().getconn()


def _put_conn(conn):
    try:
        _get_pool().putconn(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def get_db_connection():
    return _get_conn()


def close_all_connections():
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None


def invalidate_stats_cache(key=None):
    with _cache_lock:
        if key is None:
            _cache.clear()
        else:
            _cache.pop(key, None)


def cached(ttl=_CACHE_TTL, key_fn=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            cache_key = key_fn(*args, **kwargs) if key_fn else f"{fn.__name__}:{args}:{kwargs}"
            now = time.time()
            with _cache_lock:
                hit = _cache.get(cache_key)
                if hit and now - hit[0] < ttl:
                    return hit[1]
            result = fn(*args, **kwargs)
            with _cache_lock:
                _cache[cache_key] = (now, result)
            return result
        return wrapper
    return decorator


def execute_query(query, params=None, fetch=False, fetchall=False, commit=False):
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            result = None
            if fetch:
                result = cur.fetchall() if fetchall else cur.fetchone()
            if commit:
                conn.commit()
            return result
    except Exception:
        if commit:
            conn.rollback()
        raise
    finally:
        _put_conn(conn)


def execute_many(query, params_list):
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute_many(query, params_list)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _put_conn(conn)


def paginate(query, params, page=1, per_page=20, count_query=None, count_params=None):
    page = max(1, int(page or 1))
    per_page = max(1, min(int(per_page or 20), 100))

    if count_query is None:
        count_query = "SELECT COUNT(*) AS total FROM (" + query + ") AS _q"
        count_params = params
    elif count_params is None:
        count_params = params

    total_row = execute_query(count_query, count_params, fetch=True)
    total = total_row["total"] if total_row else 0

    paged_query = "SELECT * FROM (" + query + ") AS _q OFFSET %s LIMIT %s"
    rows = execute_query(paged_query, (*params, (page - 1) * per_page, per_page), fetch=True, fetchall=True)

    total_pages = (total + per_page - 1) // per_page
    return {
        "rows": rows or [],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }


def health_check():
    try:
        row = execute_query("SELECT 1 AS ok", fetch=True)
        return bool(row and row.get("ok") == 1)
    except Exception:
        return False

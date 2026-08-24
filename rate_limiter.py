import time
import logging
from threading import Lock
from functools import wraps
from flask import request, jsonify, render_template, abort

logger = logging.getLogger('antigravity.security')

class InMemoryRateLimiterStorage:
    def __init__(self):
        self._lock = Lock()
        # Storage schema: { key: [timestamp1, timestamp2, ...] }
        self._requests = {}

    def is_rate_limited(self, key, limit, period):
        """
        Sliding-window rate limit checker.
        Returns tuple: (is_limited: bool, retry_after_seconds: int)
        """
        now = time.time()
        window_start = now - period
        with self._lock:
            timestamps = self._requests.get(key, [])
            # Filter timestamps outside window
            valid_timestamps = [ts for ts in timestamps if ts > window_start]
            
            if len(valid_timestamps) >= limit:
                oldest_in_window = valid_timestamps[0]
                retry_after = int(oldest_in_window + period - now) + 1
                self._requests[key] = valid_timestamps
                return True, max(1, retry_after)
            
            valid_timestamps.append(now)
            self._requests[key] = valid_timestamps
            return False, 0

    def clear(self, scope=None):
        with self._lock:
            if scope:
                keys_to_del = [k for k in self._requests if k.startswith(f"{scope}:")]
                for k in keys_to_del:
                    del self._requests[k]
            else:
                self._requests.clear()

storage = InMemoryRateLimiterStorage()

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    else:
        ip = request.remote_addr or '127.0.0.1'
    return ip

def rate_limit(limit, period, scope=None, only_post=True):
    """
    Flask route decorator for IP & scope rate limiting.
    :param limit: Maximum requests allowed in period.
    :param period: Time window in seconds.
    :param scope: Optional scope identifier string.
    :param only_post: If True, only rate-limits POST requests (default).
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if only_post and request.method != 'POST':
                return f(*args, **kwargs)

            endpoint_scope = scope or request.endpoint or 'default'
            client_ip = get_client_ip()
            key = f"{endpoint_scope}:{client_ip}"

            is_limited, retry_after = storage.is_rate_limited(key, limit, period)
            if is_limited:
                logger.warning(f"Rate limit exceeded for IP {client_ip} on scope '{endpoint_scope}'. Retry after {retry_after}s.")
                request.rate_limit_retry_after = retry_after
                abort(429)

            return f(*args, **kwargs)
        return wrapped
    return decorator

def reset_rate_limiter(scope=None):
    """Utility to clear rate limit state during automated testing."""
    storage.clear(scope)

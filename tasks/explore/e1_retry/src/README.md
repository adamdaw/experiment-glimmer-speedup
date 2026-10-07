# httpkit

Retries are on by default (3 retries with exponential backoff).

Configure via `~/.httpkit.json`:

    {"timeout": 5, "retry": {"max_retries": 5, "backoff_base": 1.0}}

or environment variables: `HTTPKIT_TIMEOUT`, `HTTPKIT_MAX_RETRIES`, `HTTPKIT_BACKOFF_BASE`.
The server's `Retry-After` header is honored for 429 and 503 responses.

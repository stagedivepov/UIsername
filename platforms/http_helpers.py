"""Strict response handling for the new integrations; no availability inferred from blocks."""
import math

from core.config import REQUEST_TIMEOUT


def get(session, url, *, params=None, token="", proxy=None):
    headers = {"User-Agent": "UIsername/7.6 (desktop availability checker)",
               "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    return session.get(url, params=params, headers=headers,
                       proxies={"http": proxy, "https": proxy} if proxy else None,
                       timeout=REQUEST_TIMEOUT, allow_redirects=False)


def http_signal(response):
    code = response.status_code
    if code == 429:
        try:
            wait = float(response.headers.get("Retry-After", 60))
            if not math.isfinite(wait):
                wait = 60
        except (ValueError, TypeError):
            wait = 60
        return "retry", str(max(wait, 1))
    if code in (401, 402, 403):
        return "ratelimit", "Acesso recusado. Confira as credenciais e tente novamente mais tarde."
    if code == 407:
        return "badproxy", ""
    if code >= 500:
        return "retry", "10"
    if 300 <= code < 400:
        raise RuntimeError("Unexpected redirect")
    return None


def json_body(response):
    # Login pages, captcha pages and malformed responses are errors, never available.
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("Invalid JSON response") from exc

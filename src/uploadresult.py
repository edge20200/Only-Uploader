# -*- coding: utf-8 -*-
"""Reading a tracker's answer to an upload as a plain pass/fail result.

Every tracker's ``upload()`` returns ``True`` when the tracker confirmed it
accepted the upload and ``False`` otherwise, so ``upload.py`` can decide
whether the torrent may be handed to the BitTorrent client. A torrent the
tracker never accepted must not end up in the client: it announces an infohash
the tracker has never heard of and seeds nothing, while the run looks like it
succeeded.
"""

from src.console import console


class UploadResponse():
    """A tracker's answer to an upload, reduced to what callers need.

    ``accepted`` is the only field worth branching on. ``download_url`` is set
    only when the tracker accepted the upload *and* handed back a URL to fetch
    the finished torrent from.
    """

    def __init__(self, accepted, message="", download_url=None):
        self.accepted = accepted
        self.message = message
        self.download_url = download_url

    def __bool__(self):
        return self.accepted


def unit3d_upload_response(response, tracker):
    """Read a UNIT3D-style upload response and report whether it was accepted.

    UNIT3D answers with ``{"success": bool, "message": str, "data": ...}``.
    When the upload is accepted ``data`` holds the URL to download the finished
    torrent from; when it is rejected ``data`` holds per-field validation errors
    instead, so it must never be handed to an HTTP client as a URL.

    Responses with no ``success`` field at all - older forks, or a framework
    error page such as an auth failure - fall back to the HTTP status.
    """
    try:
        body = response.json()
    except ValueError:
        status = getattr(response, 'status_code', 'unknown')
        console.print(f"[bold red]{tracker} did not return JSON (HTTP {status}); the upload could not be confirmed.[/bold red]")
        return UploadResponse(False, f"Non-JSON response (HTTP {status})")

    console.print(body)

    if not isinstance(body, dict):
        console.print(f"[bold red]{tracker} returned an unexpected upload response; the upload could not be confirmed.[/bold red]")
        return UploadResponse(False, "Unexpected response shape")

    message = str(body.get('message') or "")
    data = body.get('data')

    if 'success' in body:
        accepted = bool(body['success'])
    else:
        accepted = bool(getattr(response, 'ok', True))

    if not accepted:
        console.print(f"[bold red]{tracker} rejected the upload: {message or 'no reason given'}[/bold red]")
        for detail in format_validation_errors(data):
            console.print(f"[red]  - {detail}[/red]")
        return UploadResponse(False, message)

    return UploadResponse(True, message, data if isinstance(data, str) and data else None)


def format_validation_errors(data):
    """Flatten the ``data`` of a rejected upload into printable lines.

    UNIT3D puts ``{"name": ["The name has already been taken."]}`` there, but
    forks return a bare string or a flat list just as often.
    """
    if not data:
        return []
    if isinstance(data, str):
        return [data]
    if isinstance(data, dict):
        lines = []
        for field, errors in data.items():
            if isinstance(errors, (list, tuple)):
                lines.extend(f"{field}: {error}" for error in errors)
            else:
                lines.append(f"{field}: {errors}")
        return lines
    if isinstance(data, (list, tuple)):
        return [str(error) for error in data]
    return [str(data)]


def upload_succeeded(result):
    """Interpret whatever a tracker's ``upload()`` returned.

    Tracker classes return True or False. Anything else means the class gave no
    verdict - a third-party tracker class, say - and we keep the old behaviour
    of carrying on rather than dropping an upload that may well have worked.
    """
    return result is not False

"""Server-sent events for submission notifications."""

import queue

from flask import Blueprint, Response

from api.intake_completion import _notification_listeners, _notification_lock
from api.utils import password_required_response, submissions_authorized


notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/events")
def sse_events():
    """Server-Sent Events stream for real-time doctor notifications."""
    if not submissions_authorized():
        return password_required_response()

    def stream():
        q: queue.Queue = queue.Queue(maxsize=20)
        with _notification_lock:
            _notification_listeners.append(q)
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                try:
                    data = q.get(timeout=25)
                    yield f"event: new_submission\ndata: {data}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            with _notification_lock:
                try:
                    _notification_listeners.remove(q)
                except ValueError:
                    pass

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

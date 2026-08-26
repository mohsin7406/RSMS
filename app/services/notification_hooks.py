from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.repair import RepairOrder
from app.services.sms import notify_customer

STATUS_EVENTS = {
    "Received": "received",
    "Waiting Approval": "approval_required",
    "Ready": "repair_ready",
    "Delivered": "delivered",
}


def _queue(session, event_name, repair, **values):
    if not repair or not getattr(repair, "customer", None):
        return
    queue = session.info.setdefault("sms_notifications", [])
    queue.append((event_name, repair.id, values))


@event.listens_for(Session, "before_flush")
def queue_sms_notifications(session, flush_context, instances):
    seen = session.info.setdefault("sms_notification_keys", set())

    for repair in session.dirty:
        if not isinstance(repair, RepairOrder):
            continue
        history = inspect(repair).attrs.status.history
        if not history.has_changes() or not history.added:
            continue
        new_status = history.added[0]
        event_name = STATUS_EVENTS.get(new_status)
        if event_name:
            key = ("repair_status", repair.id, new_status)
            if key not in seen:
                seen.add(key)
                _queue(session, event_name, repair)

    for payment in session.new:
        if not isinstance(payment, Payment) or payment.payment_type != "Payment":
            continue
        repair = payment.repair
        if repair is None:
            continue
        key = ("payment", payment.id or id(payment))
        if key not in seen:
            seen.add(key)
            _queue(session, "payment_received", repair, amount=f"{payment.amount:.2f}")


@event.listens_for(Session, "after_commit")
def send_queued_sms(session):
    queue = session.info.pop("sms_notifications", [])
    session.info.pop("sms_notification_keys", None)
    for event_name, repair_id, values in queue:
        repair = session.get(RepairOrder, repair_id)
        if repair is not None:
            try:
                notify_customer(event_name, repair, **values)
            except Exception:
                pass

import re
from datetime import datetime, timedelta

from app.extensions import db
from app.models import Booking, Customer, RepairOrder, User


def _login(client,user_id):
    with client.session_transaction() as session: session["user_id"]=user_id

def _csrf(client,path="/bookings/"):
    response=client.get(path);match=re.search(r'<meta name="csrf-token" content="([^"]+)"',response.get_data(as_text=True));assert match;return match.group(1)

def _booking_numbers(html):
    return re.findall(r'<td class="px-4 py-3 font-medium">(BOOK-[^<]+)</td>',html)

def test_bookings_are_paginated_and_completed_jobs_are_locked(app,client):
    with app.app_context():
        user=User(email="booking-page@example.com",role="reception");user.set_password("BookingPagePassword123!");customer=Customer(name="Paged Customer",phone="9999999999");db.session.add_all([user,customer]);db.session.flush();base=datetime(2026,8,27,10,0)
        for index in range(25):db.session.add(Booking(booking_number=f"BOOK-PAGE-{index:04d}",customer_id=customer.id,service_type="Doorstep",scheduled_at=base+timedelta(minutes=index),status="Scheduled"))
        repair=RepairOrder(job_number="JOB-HISTORY-0001",customer_id=customer.id,device="iPhone 15 Pro",issue_description="Display",service_type="Doorstep",status="Completed");db.session.add(repair);db.session.flush();history=Booking(booking_number="BOOK-HISTORY-0001",customer_id=customer.id,repair_id=repair.id,service_type="Doorstep",scheduled_at=base,status="Confirmed");db.session.add(history);db.session.commit();user_id=user.id;history_id=history.id
    _login(client,user_id)
    first=client.get("/bookings/");html=first.get_data(as_text=True);assert first.status_code==200;assert len(_booking_numbers(html))==20;assert "BOOK-HISTORY-0001" not in _booking_numbers(html)
    second=client.get("/bookings/?page=2");second_html=second.get_data(as_text=True);assert second.status_code==200;assert len(_booking_numbers(second_html))==5
    history_page=client.get("/bookings/?view=history");assert "BOOK-HISTORY-0001" in _booking_numbers(history_page.get_data(as_text=True))
    response=client.post(f"/bookings/{history_id}/status",data={"csrf_token":_csrf(client,"/bookings/?view=history"),"status":"Scheduled"},follow_redirects=False);assert response.status_code==302
    with app.app_context(): assert db.session.get(Booking,history_id).status=="Confirmed"

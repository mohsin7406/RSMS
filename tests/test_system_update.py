import io
import re

from app.extensions import db
from app.models import User


def _csrf(client,path):
    response=client.get(path); text=response.get_data(as_text=True); match=re.search(r'<meta name="csrf-token" content="([^"]+)"',text); assert match; return match.group(1)

def test_system_update_is_admin_only(app,client):
    with app.app_context():
        user=User(email="staff-update@example.com",role="staff"); user.set_password("StaffUpdatePassword123!"); db.session.add(user); db.session.commit(); uid=user.id
    with client.session_transaction() as session: session["user_id"]=uid
    assert client.get("/system-update/").status_code==403

def test_system_update_rejects_invalid_zip(app,client):
    with app.app_context():
        admin=User(email="admin-update@example.com",role="admin"); admin.set_password("AdminUpdatePassword123!"); db.session.add(admin); db.session.commit(); uid=admin.id
    with client.session_transaction() as session: session["user_id"]=uid
    token=_csrf(client,"/system-update/")
    response=client.post("/system-update/upload",data={"csrf_token":token,"package":(io.BytesIO(b"not-a-zip"),"rsms-update-9.9.9.zip")},content_type="multipart/form-data",follow_redirects=True)
    assert response.status_code==200
    assert b"Update rejected" in response.data

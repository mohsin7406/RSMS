import re

from app.extensions import db
from app.models import User


def csrf_token(client):
    response = client.get("/auth/login")
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match
    return match.group(1)


def test_post_without_csrf_is_rejected(client):
    response = client.post("/auth/login", data={"email": "a@example.com", "password": "bad"})
    assert response.status_code == 400


def test_login_sets_authenticated_session(app, client):
    with app.app_context():
        user = User(email="admin@example.com", role="admin")
        user.set_password("a-very-strong-test-password")
        db.session.add(user)
        db.session.commit()

    token = csrf_token(client)
    response = client.post(
        "/auth/login",
        data={
            "csrf_token": token,
            "email": "ADMIN@EXAMPLE.COM",
            "password": "a-very-strong-test-password",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_public_registration_is_not_available(client):
    response = client.get("/auth/register")
    assert response.status_code in {302, 403}

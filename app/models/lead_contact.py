from app.extensions import db


CONTACT_METHODS = ("Call", "WhatsApp", "SMS", "Visit", "Other")
CONTACT_OUTCOMES = ("No Answer", "Interested", "Follow Up", "Confirmed", "Not Interested", "Other")


class LeadContact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("lead.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    method = db.Column(db.String(20), nullable=False, default="Call")
    outcome = db.Column(db.String(30), nullable=False, default="Follow Up")
    notes = db.Column(db.Text, nullable=True)
    contacted_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)

    lead = db.relationship("Lead", back_populates="contacts")
    user = db.relationship("User")

from decimal import Decimal
from app.extensions import db

class SupplierPayment(db.Model):
    id=db.Column(db.Integer,primary_key=True); supplier_id=db.Column(db.Integer,db.ForeignKey('supplier.id'),nullable=False,index=True); amount=db.Column(db.Numeric(12,2),nullable=False,default=Decimal('0')); payment_date=db.Column(db.Date,nullable=False,index=True); method=db.Column(db.String(30)); reference=db.Column(db.String(100)); notes=db.Column(db.Text); created_by=db.Column(db.Integer,db.ForeignKey('user.id')); created_at=db.Column(db.DateTime,server_default=db.func.now(),nullable=False)
    supplier=db.relationship('Supplier',backref=db.backref('payments',lazy=True)); creator=db.relationship('User')

class Expense(db.Model):
    id=db.Column(db.Integer,primary_key=True); expense_date=db.Column(db.Date,nullable=False,index=True); category=db.Column(db.String(50),nullable=False,index=True); amount=db.Column(db.Numeric(12,2),nullable=False,default=Decimal('0')); repair_id=db.Column(db.Integer,db.ForeignKey('repair_order.id'),index=True); description=db.Column(db.String(255),nullable=False); payment_method=db.Column(db.String(30)); reference=db.Column(db.String(100)); created_by=db.Column(db.Integer,db.ForeignKey('user.id')); created_at=db.Column(db.DateTime,server_default=db.func.now(),nullable=False)
    repair=db.relationship('RepairOrder',backref=db.backref('expenses',lazy=True)); creator=db.relationship('User')

class StockAllocation(db.Model):
    id=db.Column(db.Integer,primary_key=True); part_id=db.Column(db.Integer,db.ForeignKey('part.id'),nullable=False,index=True); repair_id=db.Column(db.Integer,db.ForeignKey('repair_order.id'),nullable=False,index=True); technician_id=db.Column(db.Integer,db.ForeignKey('user.id'),index=True); quantity=db.Column(db.Numeric(12,2),nullable=False,default=Decimal('0')); status=db.Column(db.String(30),nullable=False,default='Reserved',index=True); notes=db.Column(db.Text); created_by=db.Column(db.Integer,db.ForeignKey('user.id')); created_at=db.Column(db.DateTime,server_default=db.func.now(),nullable=False); updated_at=db.Column(db.DateTime,server_default=db.func.now(),onupdate=db.func.now(),nullable=False)
    part=db.relationship('Part'); repair=db.relationship('RepairOrder',backref=db.backref('stock_allocations',lazy=True)); technician=db.relationship('User',foreign_keys=[technician_id]); creator=db.relationship('User',foreign_keys=[created_by])

class AuditEvent(db.Model):
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey('user.id'),index=True); action=db.Column(db.String(80),nullable=False,index=True); entity_type=db.Column(db.String(50),nullable=False,index=True); entity_id=db.Column(db.Integer,index=True); details=db.Column(db.Text); created_at=db.Column(db.DateTime,server_default=db.func.now(),nullable=False,index=True)
    user=db.relationship('User')

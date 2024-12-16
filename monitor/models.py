from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class MonitorConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    system = db.Column(db.String(100), nullable=False, default='默认系统')
    host = db.Column(db.String(100), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    user = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)
    database = db.Column(db.String(100), nullable=False)
    env = db.Column(db.String(50), nullable=False)
    query = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 
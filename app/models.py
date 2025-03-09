from datetime import datetime
from app import db
from flask_login import UserMixin
from flask import current_app
from itsdangerous import URLSafeTimedSerializer as Serializer

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    selected_fiat = db.Column(db.String(10), nullable=False, default="USD")  # USD, EUR, etc.
    
    # Relationship to wallets
    wallets = db.relationship("Wallet", backref="user", lazy=True)

    def __repr__(self):
        return f"<User {self.username}>"
    
    def get_id(self):
        return str(self.id)

    def get_reset_token(self, expires_sec=1800):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_reset_token(token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token)['user_id']
        except:
            return None
        return User.query.get(user_id)

class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    wallet_name = db.Column(db.String(100), nullable=False)
    
    # Relationship to transactions
    transactions = db.relationship("Transaction", backref="wallet", lazy=True)

    def __repr__(self):
        return f"<Wallet {self.wallet_name} of User {self.user_id}>"

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    wallet_id = db.Column(db.Integer, db.ForeignKey("wallet.id"), nullable=False)
    datetime = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    type = db.Column(db.Enum("buy", "sell", "spend", "earn", name="transaction_type"), nullable=False)
    sats = db.Column(db.BigInteger, nullable=False)  # Sats involved in transaction
    fiat_amount = db.Column(db.Float, nullable=False)  # Fiat value at transaction time
    sats_per_fiat = db.Column(db.Float, nullable=False)  # Fiat price per sat at time of transaction
    notes = db.Column(db.String(255), nullable=True)  # Optional description

    def __repr__(self):
        return f"<Transaction {self.type} {self.sats} sats for {self.fiat_amount} {self.price_per_sat}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "wallet_id": self.wallet_id,
            "datetime": self.datetime.strftime('%Y-%m-%d %H:%M:%S'),  # Format date
            "type": self.type,
            "sats": self.sats,
            "fiat_amount": self.fiat_amount,
            "sats_per_fiat": self.sats_per_fiat,
            "notes": self.notes,
        }

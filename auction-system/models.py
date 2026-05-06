from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'Users'
    UserID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Username = db.Column(db.String(50), unique=True, nullable=False)
    Email = db.Column(db.String(100), unique=True, nullable=False)
    PasswordHash = db.Column(db.String(255), nullable=False)
    Contact = db.Column(db.String(15))
    Role = db.Column(db.Enum('admin', 'user'), default='user')
    RegistrationDate = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    
    # Relationships
    items = db.relationship('Item', backref='seller', lazy=True, foreign_keys='Item.SellerID')
    bids = db.relationship('Bid', backref='bidder', lazy=True)
    
    def set_password(self, password):
        self.PasswordHash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.PasswordHash, password)

class Item(db.Model):
    __tablename__ = 'Items'
    ItemID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ItemName = db.Column(db.String(100), nullable=False)
    Description = db.Column(db.Text)
    StartingBid = db.Column(db.Numeric(10, 2), nullable=False)
    SellerID = db.Column(db.Integer, db.ForeignKey('Users.UserID'), nullable=False)
    CategoryID = db.Column(db.Integer)
    ImagePath = db.Column(db.String(255))  # NEW: stores path like "uploads/filename.jpg"
    ListedDate = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    
    # Relationships
    auctions = db.relationship('Auction', backref='item', lazy=True)

class Auction(db.Model):
    __tablename__ = 'Auctions'
    AuctionID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ItemID = db.Column(db.Integer, db.ForeignKey('Items.ItemID'), nullable=False)
    StartTime = db.Column(db.DateTime, nullable=False)
    EndTime = db.Column(db.DateTime, nullable=False)
    Status = db.Column(db.Enum('Open', 'Closed'), default='Open')
    CreatedBy = db.Column(db.Integer, db.ForeignKey('Users.UserID'), nullable=False)
    WinnerID = db.Column(db.Integer, db.ForeignKey('Users.UserID'))
    
    # Relationships
    bids = db.relationship('Bid', backref='auction', lazy=True)
    creator = db.relationship('User', foreign_keys=[CreatedBy])
    winner = db.relationship('User', foreign_keys=[WinnerID])

class Bid(db.Model):
    __tablename__ = 'Bids'
    BidID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    AuctionID = db.Column(db.Integer, db.ForeignKey('Auctions.AuctionID'), nullable=False)
    UserID = db.Column(db.Integer, db.ForeignKey('Users.UserID'), nullable=False)
    Amount = db.Column(db.Numeric(10, 2), nullable=False)
    BidTime = db.Column(db.TIMESTAMP, default=datetime.utcnow)

class Payment(db.Model):
    __tablename__ = 'Payments'
    PaymentID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    AuctionID = db.Column(db.Integer, db.ForeignKey('Auctions.AuctionID'), nullable=False)
    UserID = db.Column(db.Integer, db.ForeignKey('Users.UserID'), nullable=False)
    Amount = db.Column(db.Numeric(10, 2), nullable=False)
    PaymentMethod = db.Column(db.Enum('COD', 'UPI', 'Card'), nullable=False)
    PaymentStatus = db.Column(db.Enum('Pending', 'Completed'), default='Pending')
    TransactionTime = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    
    # Relationships
    shipping = db.relationship('Shipping', backref='payment', lazy=True)

class Shipping(db.Model):
    __tablename__ = 'Shipping'
    ShippingID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    PaymentID = db.Column(db.Integer, db.ForeignKey('Payments.PaymentID'), nullable=False)
    Address = db.Column(db.Text, nullable=False)
    Method = db.Column(db.Enum('Express', 'Standard'), nullable=False)
    Cost = db.Column(db.Numeric(10, 2), nullable=False)
    Status = db.Column(db.Enum('Processing', 'Shipped', 'Delivered'), default='Processing')
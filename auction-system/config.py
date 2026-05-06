import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'auction-system-secret-key'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:Samruddhi%4024@localhost/AuctionDB'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload

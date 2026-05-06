from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    admin = User.query.filter_by(Email='admin@auction.com').first()
    admin.PasswordHash = generate_password_hash('adminpass')
    db.session.commit()
    print("Admin password fixed!")
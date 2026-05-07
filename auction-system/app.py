import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, User, Item, Auction, Bid, Payment, Shipping
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import desc, func, text 
import os

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

def update_auction_winners():
    """Assign winners to closed auctions that don't have a winner yet"""
    try:
        closed_auctions = Auction.query.filter_by(Status='Closed', WinnerID=None).all()
        for auction in closed_auctions:
            highest_bid = db.session.query(
                Bid.UserID, func.max(Bid.Amount)
            ).filter(Bid.AuctionID == auction.AuctionID).group_by(Bid.UserID).order_by(func.max(Bid.Amount).desc()).first()
            if highest_bid:
                auction.WinnerID = highest_bid[0]
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating winners: {str(e)}")

@app.before_request
def update_auction_statuses():
    """Update auction statuses and assign winners before processing requests"""
    try:
        if not request.path.startswith('/static/'):
            db.session.execute(
                text('UPDATE Auctions SET Status = "Closed" WHERE EndTime < NOW() AND Status = "Open"')
            )
            db.session.commit()
            update_auction_winners()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating auction statuses: {str(e)}")

def create_admin():
    """Auto-create or fix admin account on startup"""
    with app.app_context():
        admin = User.query.filter_by(Email='admin@auction.com').first()
        if not admin:
            admin = User(
                Username='admin',
                Email='admin@auction.com',
                Role='admin',
                PasswordHash=generate_password_hash('adminpass')
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin created!")
        elif not check_password_hash(admin.PasswordHash, 'adminpass'):
            admin.PasswordHash = generate_password_hash('adminpass')
            db.session.commit()
            print("Admin password fixed!")
        else:
            print("Admin account OK!")

# Authentication middleware
@app.before_request
def require_login():
    allowed_routes = ['login', 'register', 'index', 'static']
    if request.endpoint not in allowed_routes and 'user_id' not in session and not request.path.startswith('/static/'):
        return redirect(url_for('login'))

# Utility function to get current datetime in UTC
@app.context_processor
def utility_processor():
    def now():
        return datetime.utcnow()
    return dict(now=now, timedelta=timedelta)


# Home route
@app.route('/')
def index():
    active_auctions = db.session.query(
        Auction, Item, func.coalesce(func.max(Bid.Amount), Item.StartingBid).label('current_bid')
    ).join(Item, Auction.ItemID == Item.ItemID
    ).outerjoin(Bid, Auction.AuctionID == Bid.AuctionID
    ).filter(Auction.Status == 'Open'
    ).group_by(Auction.AuctionID
    ).order_by(Auction.EndTime
    ).limit(6).all()
    return render_template('base.html', auctions=active_auctions, title="Online Auction System")

# User authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(Email=email).first()
        if user and check_password_hash(user.PasswordHash, password):
            session['user_id'] = user.UserID
            session['username'] = user.Username
            session['role'] = user.Role
            flash('Login successful!', 'success')
            if user.Role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    return render_template('auth/login.html', title="Login")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        contact = request.form.get('contact')
        existing_user = User.query.filter(
            (User.Username == username) | (User.Email == email)
        ).first()
        if existing_user:
            flash('Username or email already exists', 'danger')
            return render_template('auth/register.html')
        new_user = User(
            Username=username,
            Email=email,
            Contact=contact,
            PasswordHash=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please login', 'success')
        return redirect(url_for('login'))
    return render_template('auth/register.html', title="Register")

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

# ── ADMIN ROUTES ────────────────────────────────────────────────────────────

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))

    # Include winner user info in query
    WinnerUser = db.aliased(User)
    auctions = db.session.query(
        Auction, Item, User, WinnerUser
    ).join(Item, Auction.ItemID == Item.ItemID
    ).join(User, Item.SellerID == User.UserID
    ).outerjoin(WinnerUser, Auction.WinnerID == WinnerUser.UserID
    ).order_by(Auction.EndTime.desc()).all()

    return render_template('admin/dashboard.html', auctions=auctions, title="Admin Dashboard")

@app.route('/admin/view_auction/<int:auction_id>')
def admin_view_auction(auction_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))

    auction_details = db.session.query(
        Auction,
        Item,
        func.coalesce(func.max(Bid.Amount), Item.StartingBid).label('current_bid')
    ).join(
        Item, Auction.ItemID == Item.ItemID
    ).outerjoin(
        Bid, Auction.AuctionID == Bid.AuctionID
    ).filter(
        Auction.AuctionID == auction_id
    ).group_by(
        Auction.AuctionID
    ).first()

    if not auction_details:
        flash('Auction not found', 'danger')
        return redirect(url_for('admin_dashboard'))

    auction, item, current_bid = auction_details

    bid_history = db.session.query(
        Bid, User
    ).join(
        User, Bid.UserID == User.UserID
    ).filter(
        Bid.AuctionID == auction_id
    ).order_by(
        Bid.BidTime.desc()
    ).all()

    return render_template(
        'admin/view_auction.html',
        auction=auction,
        item=item,
        current_bid=current_bid,
        bid_history=bid_history,
        title="View Auction"
    )

@app.route('/admin/create_auction', methods=['GET', 'POST'])
def create_auction():
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        item_id = request.form.get('item_id')
        start_time = datetime.strptime(request.form.get('start_time'), '%Y-%m-%dT%H:%M')
        end_time = datetime.strptime(request.form.get('end_time'), '%Y-%m-%dT%H:%M')
        if end_time <= start_time:
            flash('End time must be after start time', 'danger')
            items = Item.query.all()
            return render_template('admin/create_auction.html', items=items)
        try:
            db.session.execute(
              text('CALL CreateAuction(:p_ItemID, :p_StartTime, :p_EndTime, :p_AdminID)'),
              {
                  'p_ItemID': item_id,
                  'p_StartTime': start_time,
                  'p_EndTime': end_time,
                  'p_AdminID': session.get('user_id')
             }
            )
            db.session.commit()
            flash('Auction created successfully', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating auction: {str(e)}', 'danger')
    available_items = db.session.query(Item).outerjoin(
        Auction, (Item.ItemID == Auction.ItemID) & (Auction.Status == 'Open')
    ).filter(Auction.AuctionID == None).all()
    return render_template('admin/create_auction.html', items=available_items, title="Create Auction")

@app.route('/admin/create_item', methods=['GET', 'POST'])
def create_new_item():
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        item_name = request.form.get('item_name')
        description = request.form.get('description')
        starting_bid = request.form.get('starting_bid')
        category = request.form.get('category') or None
        seller_id = session.get('user_id')

        # Handle image upload
        image_path = None
        if 'item_image' in request.files:
            file = request.files['item_image']
            if file and file.filename != '':
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
                upload_folder = os.path.join('static', 'uploads')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, filename))
                image_path = f"uploads/{filename}"

        try:
            new_item = Item(
                ItemName=item_name,
                Description=description,
                StartingBid=starting_bid,
                SellerID=seller_id,
                CategoryID=category,
                ImagePath=image_path
            )
            db.session.add(new_item)
            db.session.commit()
            flash('Item created successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating item: {str(e)}', 'danger')
    return render_template('admin/create_item.html', title="Create Item")

@app.route('/admin/manage_items')
def manage_items():
    if session.get('role') != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    items = Item.query.all()
    return render_template('admin/manage_items.html', items=items, title="Manage Items")

# ── USER ROUTES ─────────────────────────────────────────────────────────────

@app.route('/user/dashboard')
def user_dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    # Block admin from user dashboard
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))

    # Get highest bid per auction to detect outbid status
    highest_bids_map = {
        row[0]: row[1]
        for row in db.session.query(Bid.AuctionID, func.max(Bid.Amount)).group_by(Bid.AuctionID).all()
    }

    # Get user's bids and tag each with is_outbid flag
    user_bids_raw = db.session.query(
        Bid, Auction, Item
    ).join(Auction, Bid.AuctionID == Auction.AuctionID
    ).join(Item, Auction.ItemID == Item.ItemID
    ).filter(Bid.UserID == user_id
    ).order_by(Bid.BidTime.desc()).all()

    user_bids = []
    for bid, auction, item in user_bids_raw:
        bid.is_outbid = (
            highest_bids_map.get(auction.AuctionID) is not None and
            bid.Amount < highest_bids_map.get(auction.AuctionID)
        )
        user_bids.append((bid, auction, item))

    won_auctions_raw = db.session.query(
        Auction, Item, func.max(Bid.Amount).label('highest_bid')
    ).join(Item, Auction.ItemID == Item.ItemID
    ).join(Bid, Auction.AuctionID == Bid.AuctionID
    ).filter(Auction.WinnerID == user_id
    ).group_by(Auction.AuctionID
    ).order_by(Auction.EndTime.desc()).all()

    user_payments_map = {
        p.AuctionID: p
        for p in Payment.query.filter_by(UserID=user_id).all()
    }

    won_auctions = [
        (auction, item, highest_bid, user_payments_map.get(auction.AuctionID))
        for auction, item, highest_bid in won_auctions_raw
    ]

    active_auctions = db.session.query(
        Auction, Item, func.coalesce(func.max(Bid.Amount), Item.StartingBid).label('highest_bid')
    ).join(Item, Auction.ItemID == Item.ItemID
    ).outerjoin(Bid, Auction.AuctionID == Bid.AuctionID
    ).filter(Auction.Status == 'Open'
    ).group_by(Auction.AuctionID
    ).order_by(Auction.EndTime).all()

    payments = db.session.query(
        Payment, Item.ItemName
    ).join(Auction, Payment.AuctionID == Auction.AuctionID
    ).join(Item, Auction.ItemID == Item.ItemID
    ).filter(Payment.UserID == user_id).all()

    shippings = db.session.query(
        Shipping, Item.ItemName
    ).join(Payment, Shipping.PaymentID == Payment.PaymentID
    ).join(Auction, Payment.AuctionID == Auction.AuctionID
    ).join(Item, Auction.ItemID == Item.ItemID
    ).filter(Payment.UserID == user_id).all()

    return render_template('user/dashboard.html',
                          user_bids=user_bids,
                          won_auctions=won_auctions,
                          active_auctions=active_auctions,
                          payments=payments,
                          shippings=shippings,
                          title="User Dashboard")

@app.route('/user/bid/<int:auction_id>', methods=['GET', 'POST'])
def bid(auction_id):
    # Block admin from bidding
    if session.get('role') == 'admin':
        flash('Admins are not allowed to place bids', 'danger')
        return redirect(url_for('admin_dashboard'))

    user_id = session.get('user_id')

    auction_details = db.session.query(
        Auction, Item, func.coalesce(func.max(Bid.Amount), Item.StartingBid).label('current_bid')
    ).join(Item, Auction.ItemID == Item.ItemID
    ).outerjoin(Bid, Auction.AuctionID == Bid.AuctionID
    ).filter(Auction.AuctionID == auction_id
    ).group_by(Auction.AuctionID).first()

    if not auction_details:
        flash('Auction not found', 'danger')
        return redirect(url_for('user_dashboard'))

    auction, item, current_bid = auction_details

    if auction.Status != 'Open' or auction.EndTime < datetime.utcnow():
        flash('This auction is no longer active', 'warning')
        return redirect(url_for('user_dashboard'))

    if request.method == 'POST':
        bid_amount = Decimal(request.form.get('bid_amount'))
        try:
            db.session.execute(
              text('SELECT Status FROM Auctions WHERE AuctionID = :auction_id FOR UPDATE'),
              {'auction_id': auction_id}
            )
            db.session.execute(
                text('CALL PlaceBid(:p_AuctionID, :p_UserID, :p_Amount)'),
                {
                    'p_AuctionID': auction_id,
                    'p_UserID': user_id,
                    'p_Amount': bid_amount
                }
            )
            db.session.commit()
            flash('Bid placed successfully', 'success')
            return redirect(url_for('bid', auction_id=auction_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error placing bid: {str(e)}', 'danger')

    bid_history = Bid.query.filter_by(
        AuctionID=auction_id
    ).order_by(Bid.BidTime.desc()).all()

    return render_template('user/bid.html',
                          auction=auction,
                          item=item,
                          current_bid=current_bid,
                          bid_history=bid_history,
                          title="Place Bid")

# ── PAYMENT & SHIPPING ───────────────────────────────────────────────────────

@app.route('/payment/<int:auction_id>', methods=['GET', 'POST'])
def payment(auction_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    auction_details = db.session.query(
        Auction, Item, func.max(Bid.Amount).label('winning_bid')
    ).join(Item, Auction.ItemID == Item.ItemID
    ).join(Bid, Auction.AuctionID == Bid.AuctionID
    ).filter(Auction.AuctionID == auction_id, Auction.WinnerID == user_id
    ).group_by(Auction.AuctionID).first()

    if not auction_details:
        flash('You are not the winner of this auction or auction not found', 'danger')
        return redirect(url_for('user_dashboard'))

    auction, item, winning_bid = auction_details

    existing_payment = Payment.query.filter_by(
        AuctionID=auction_id,
        UserID=user_id
    ).first()

    if existing_payment:
        return redirect(url_for('payment_details', payment_id=existing_payment.PaymentID))

    if request.method == 'POST':
        try:
            new_payment = Payment(
                AuctionID=auction_id,
                UserID=user_id,
                Amount=winning_bid,
                PaymentMethod=request.form.get('payment_method'),
                PaymentStatus='Completed'
            )
            db.session.add(new_payment)
            db.session.commit()
            flash('Payment successful!', 'success')
            return redirect(url_for('shipping', payment_id=new_payment.PaymentID))
        except Exception as e:
            db.session.rollback()
            flash(f'Payment failed: {str(e)}', 'danger')

    return render_template('payment.html', item=item, winning_bid=winning_bid)

@app.route('/payment/details/<int:payment_id>')
def payment_details(payment_id):
    user_id = session.get('user_id')
    payment = Payment.query.get_or_404(payment_id)
    if payment.UserID != user_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('user_dashboard'))
    auction = Auction.query.get(payment.AuctionID)
    item = Item.query.get(auction.ItemID)
    shipping = Shipping.query.filter_by(PaymentID=payment_id).first()
    return render_template('user/payment_details.html',
                          payment=payment, auction=auction, item=item, shipping=shipping)

@app.route('/shipping/<int:payment_id>', methods=['GET', 'POST'])
def shipping(payment_id):
    user_id = session.get('user_id')
    payment = Payment.query.get_or_404(payment_id)
    if payment.UserID != user_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('user_dashboard'))
    auction = Auction.query.get(payment.AuctionID)
    item = Item.query.get(auction.ItemID)
    existing_shipping = Shipping.query.filter_by(PaymentID=payment_id).first()
    if existing_shipping:
        return redirect(url_for('shipping_details', shipping_id=existing_shipping.ShippingID))
    if request.method == 'POST':
        try:
            shipping_cost = 100 if request.form.get('shipping_method') == 'Express' else 50
            new_shipping = Shipping(
                PaymentID=payment_id,
                Address=request.form.get('address'),
                Method=request.form.get('shipping_method'),
                Cost=shipping_cost,
                Status='Processing'
            )
            db.session.add(new_shipping)
            db.session.commit()
            flash('Shipping details saved successfully', 'success')
            return redirect(url_for('shipping_details', shipping_id=new_shipping.ShippingID))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving shipping details: {str(e)}', 'danger')
    return render_template('shipping.html', payment=payment, item=item)

@app.route('/shipping/details/<int:shipping_id>')
def shipping_details(shipping_id):
    user_id = session.get('user_id')
    shipping = Shipping.query.get_or_404(shipping_id)
    payment = Payment.query.get(shipping.PaymentID)
    if payment.UserID != user_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('user_dashboard'))
    auction = Auction.query.get(payment.AuctionID)
    item = Item.query.get(auction.ItemID)
    return render_template('user/shipping_details.html',
                          shipping=shipping, payment=payment, auction=auction, item=item)

# Initialize database and run app
# Initialize database and run app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    create_admin()

    port = int(os.environ.get('PORT', 5000))

    app.run(host='0.0.0.0', port=port, debug=False)
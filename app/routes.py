from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, g, session, current_app
from flask_login import login_required, current_user, login_user, logout_user, login_manager
from flask_mail import Message
from flask_babel import get_locale
from app import db, mail
from app.models import Wallet, Transaction, User
from app.utils import generate_pdf, calculate_tax_report_data, get_btc_price
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO
from decimal import Decimal
import requests

bp = Blueprint("main", __name__)

@bp.route('/')
def home():
    return redirect(url_for('main.dashboard'))

@bp.route("/dashboard", methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        # Get the selected fiat from the form
        selected_fiat = request.form.get('fiat')

        # Check if the fiat is valid (in case you have more fiats to add)
        if selected_fiat in ['USD', 'EUR', 'CHF', 'GBP']:  # Add more fiats if needed
            # Update the selected_fiat field for the current user
            current_user.selected_fiat = selected_fiat
            db.session.commit()  # Commit the change to the database
            
            flash('Fiat currency updated successfully!', 'success')
        else:
            flash('Invalid fiat currency selected. Please try again.', 'danger')
        
        return redirect(url_for('main.dashboard'))
        
    # Fetch user's selected fiat (or default to USD if not set)
    selected_fiat = current_user.selected_fiat if current_user.selected_fiat else 'USD'

    # Fetch user wallets and transactions
    wallets = Wallet.query.filter_by(user_id=current_user.id).all()
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.datetime.desc()).all()

    return render_template("dashboard.html", selected_fiat=selected_fiat, wallets=wallets, transactions=transactions)

@bp.route("/new_transaction", methods=["GET", "POST"])
@login_required
def new_transaction():
    if request.method == "POST":
        wallet_id = request.form.get("wallet")
        date_time_str = request.form['date_time']
        date_time = datetime.strptime(date_time_str, '%Y-%m-%dT%H:%M')
        type = request.form.get("type")  # buy, sell, spend, earn
        sats = int(request.form.get("sats"))
        fiat_amount = float(request.form.get("fiat_amount"))
        sats_per_fiat = sats / fiat_amount if sats > 0 else 0
        notes = request.form.get("notes", "")

        # Validate input
        if not wallet_id or not type or sats <= 0 or fiat_amount < 0:
            flash("Invalid transaction details", "danger")
            return redirect(url_for("main.new_transaction"))

        # Create transaction
        transaction = Transaction(
            user_id=current_user.id,
            wallet_id=wallet_id,
            datetime=date_time,
            type=type,
            sats=sats,
            fiat_amount=fiat_amount,
            sats_per_fiat=sats_per_fiat,
            notes=notes
        )
        db.session.add(transaction)
        db.session.commit()

        flash("Transaction added successfully", "success")
        return redirect(url_for("main.dashboard"))

    # Fetch user wallets for dropdown selection
    wallets = Wallet.query.filter_by(user_id=current_user.id).all()
    return render_template("new_transaction.html", wallets=wallets)

@bp.route('/edit_transaction/<int:transaction_id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(transaction_id):
    # Fetch the transaction by ID
    transaction = Transaction.query.get_or_404(transaction_id)

    # Check if the transaction belongs to the logged-in user
    if transaction.user_id != current_user.id:
        flash('You do not have permission to edit this transaction.', 'danger')
        return redirect(url_for('main.dashboard'))

    # Fetch wallets associated with the logged-in user
    wallets = Wallet.query.filter_by(user_id=current_user.id).all()

    if request.method == 'POST':
        # Retrieve form data
        date_time_str = request.form['date_time']
        date_time = datetime.strptime(date_time_str, '%Y-%m-%dT%H:%M')
        wallet_id = request.form['wallet']
        transaction_type = request.form['type']
        sats = int(request.form['sats'])
        fiat_amount = float(request.form['fiat_amount'])
        sats_per_fiat = sats / fiat_amount if sats > 0 else 0
        notes = request.form.get('notes', '')

        # Update the transaction with the new values
        transaction.datetime = date_time
        transaction.wallet_id = wallet_id
        transaction.type = transaction_type
        transaction.sats = sats
        transaction.fiat_amount = fiat_amount
        transaction.sats_per_fiat = sats_per_fiat
        transaction.notes = notes

        # Commit the changes to the database
        db.session.commit()

        flash('Transaction updated successfully!', 'success')
        return redirect(url_for('main.dashboard'))

    # If GET request, render the form
    return render_template('edit_transaction.html', transaction=transaction, wallets=wallets)

@bp.route("/wallets")
@login_required
def wallets():
    wallets = Wallet.query.filter_by(user_id=current_user.id).all()
    return render_template("wallets.html", wallets=wallets)

@bp.route("/delete_transaction/<int:transaction_id>", methods=["POST"])
@login_required
def delete_transaction(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)

    if transaction.user_id != current_user.id:
        flash("Unauthorized action", "danger")
        return redirect(url_for("main.dashboard"))

    db.session.delete(transaction)
    db.session.commit()
    flash("Transaction deleted successfully", "success")
    return redirect(url_for("main.dashboard"))

@bp.route("/add_wallet", methods=["POST"])
@login_required
def add_wallet():
    wallet_name = request.form.get("wallet_name")

    if not wallet_name:
        flash("Wallet name cannot be empty.", "danger")
        return redirect(url_for("main.dashboard"))

    new_wallet = Wallet(user_id=current_user.id, wallet_name=wallet_name)
    db.session.add(new_wallet)
    db.session.commit()

    flash(f"Wallet '{wallet_name}' added successfully!", "success")
    return redirect(url_for("main.dashboard"))


@bp.route("/delete_wallet/<int:wallet_id>", methods=["POST"])
@login_required
def delete_wallet(wallet_id):
    wallet = Wallet.query.get_or_404(wallet_id)

    if wallet.user_id != current_user.id:
        flash("Unauthorized action", "danger")
        return redirect(url_for("main.dashboard"))

    db.session.delete(wallet)
    db.session.commit()

    flash(f"Wallet '{wallet.wallet_name}' deleted successfully!", "success")
    return redirect(url_for("main.dashboard"))

@bp.route("/btc_price/<currency>")
@login_required
def btc_price(currency):
    # Define the endpoint for CoinGecko (Hourly for last 365 days)
    api_url_last_year = f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency={currency}&days=90"
    
    # Define the endpoint for CryptoCompare (Daily for older data)
    now = datetime.utcnow()
    date_cutoff = now - timedelta(days=90)
    api_url_old_data = f"https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym={currency}&limit=2000&toTs={int(date_cutoff.timestamp())}"
    
    try:
        # Fetch CoinGecko hourly data for the last year
        response_last_year = requests.get(api_url_last_year)
        data_last_year = response_last_year.json()
        
        # Fetch CryptoCompare daily data for older data
        response_old_data = requests.get(api_url_old_data)
        data_old = response_old_data.json()
        
        # Prepare the chart data list
        chart_data = []
        
        # Process CoinGecko hourly data
        for item in data_last_year['prices']:
            timestamp, price = item
            chart_data.append({"time": timestamp, "price": price})
        
        # Process CryptoCompare daily data
        for item in data_old['Data']['Data']:
            timestamp, price = item["time"], item["close"]
            chart_data.append({"time": timestamp * 1000, "price": price}) # Convert time to milliseconds (Coingecko data is that already)
        
        # Sort the combined data by time (to ensure it's in chronological order)
        chart_data.sort(key=lambda x: x['time'])

        return jsonify({"prices": chart_data})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/transactions/<int:wallet_id>')
@login_required
def get_wallet_transactions(wallet_id):
    # Get the selected wallet and ensure it belongs to the current user
    wallet = Wallet.query.get_or_404(wallet_id)
    if wallet.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403

    # Get transactions for the wallet
    transactions = Transaction.query.filter_by(wallet_id=wallet_id).order_by(Transaction.datetime.desc()).all()

    # Format transactions into a dictionary for easy consumption by the frontend
    transaction_data = [
        {
            'id': transaction.id,
            'type': transaction.type,
            'amount': transaction.sats,
            'date': transaction.datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'fiat_amount': transaction.fiat_amount,
            'sats_per_fiat': transaction.sats_per_fiat,
            'notes': transaction.notes
        }
        for transaction in transactions
    ]

    return jsonify(transaction_data)

@bp.route('/api/get_transactions')
@login_required
def api_get_transactions():
    # Get Transactions from the database
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    transactions_dict = [tx.to_dict() for tx in transactions]

    return jsonify(transactions_dict)

@bp.route('/tax-report', methods=['GET', 'POST'])
@login_required
def tax_report():
    """Render tax report form and generate PDF."""
    # Get available tax years based on user's transactions
    years = Transaction.query.filter_by(user_id=current_user.id).with_entities(Transaction.datetime).distinct()
    available_years = sorted(set(tx.datetime.year for tx in years if tx.datetime.year < datetime.now().year), reverse=True)

    if request.method == 'POST':
        tax_year = int(request.form['tax_year'])
        language = request.form['language']
        name = request.form['name']
        address = request.form['address']
        admin_cost = Decimal(request.form['admin_cost']) if request.form['admin_cost'] else Decimal(0)
        admin_desc = request.form['admin_desc']
        fiat_currency = current_user.selected_fiat

        # Fetch transactions and calculate values
        report_data = calculate_tax_report_data(tax_year)

        # Generate PDF
        pdf = generate_pdf(language, name, address, admin_cost, admin_desc, fiat_currency, report_data, tax_year)

        # Send the file as a downloadable response
        return send_file(BytesIO(pdf), mimetype='application/pdf', as_attachment=True, download_name=f"Bitcoin_Tax_Report_{name}_{tax_year}.pdf")

    return render_template("tax_report.html", available_years=available_years)   

# Login routes

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        email = request.form['email']  # Make sure you're getting email too

        # Check if the username or email already exists in the database
        existing_user = User.query.filter_by(username=username).first()
        existing_email = User.query.filter_by(email=email).first()

        if existing_user:
            flash('Username is already taken. Please choose a different one.', 'error')
            return redirect(url_for('main.register'))

        if existing_email:
            flash('This email is already registered.', 'error')
            return redirect(url_for('main.register'))

        # If the username is available, create the new user
        new_user = User(username=username, password=password,
                        email=email)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.')
        return redirect(url_for('main.login'))

    return render_template('register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)  # This logs the user in
            flash('Login successful!')
            return redirect(url_for('main.dashboard'))

        flash('Invalid credentials. Please try again.')
    return render_template('login.html')

@bp.route('/logout')
def logout():
    logout_user()  # This logs the user out
    flash('You have been logged out.')
    return redirect(url_for('main.login'))

@bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()

        if user:
            token = user.get_reset_token()
            reset_url = url_for('main.reset_password', token=token, _external=True)
            msg = Message('Password Reset Request', recipients=[email])
            msg.body = f'To reset your password, visit the following link: {reset_url}'
            mail.send(msg)

            flash('An email with a password reset link has been sent.', 'info')
            return redirect(url_for('main.login'))
        else:
            flash('No account found with that email.', 'error')

    return render_template('forgot_password.html')

@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.verify_reset_token(token)
    if user is None:
        flash('The reset token is invalid or expired.', 'error')
        return redirect(url_for('main.forgot_password'))

    if request.method == 'POST':
        password = generate_password_hash(request.form['password'])
        user.password = password
        db.session.commit()
        flash('Your password has been updated!', 'success')
        return redirect(url_for('main.login'))

    return render_template('reset_password.html')
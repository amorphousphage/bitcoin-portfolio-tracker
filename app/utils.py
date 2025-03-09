from weasyprint import HTML
from flask_login import current_user
from flask import render_template
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from app import db
from app.models import Wallet, Transaction, User
from app.translations import translations
import requests

MONTHS = {
    'en': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    'de': ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'],
    'fr': ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jui', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc'],
    'it': ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic'],
    'es': ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
}

def generate_pdf(language, name, address, admin_cost, admin_desc, fiat_currency, report_data, tax_year):
    # Get the list of months for the selected language
    months = MONTHS.get(language, MONTHS['en'])  # Default to 'en' if language is not found
    
    # Get the current date with localized month abbreviation
    current_date = datetime.now().strftime(f"%d-{months[datetime.now().month-1]}-%Y")
    
    # Generates a PDF from HTML template with report data
    html_template = render_template("tax_report_pdf.html", 
        name=name, address=address, admin_cost=admin_cost, admin_desc=admin_desc,
        fiat_currency=fiat_currency, report_data=report_data, tax_year=tax_year, one_eight=Decimal(1e8), translations=translations[language], current_date=current_date
    )

    pdf = HTML(string=html_template).write_pdf()
    return pdf

def calculate_tax_report_data(tax_year):
        """Fetches and calculates required tax data for a given year."""
        first_year_of_buying = False
        start_date = datetime(tax_year, 1, 1, 0, 0, 0)
        end_date = datetime(tax_year, 12, 31, 23, 59, 59)

        # Get balance at start of the year
        sats_start = (
            db.session.query(
                db.func.sum(
                    db.case(
                        (Transaction.type.in_(["buy", "earn"]), Transaction.sats),
                        (Transaction.type.in_(["sell", "spend"]), -Transaction.sats),
                        else_=0
                    )
                )
            )
            .filter(Transaction.datetime < start_date, Transaction.user_id == current_user.id)
            .scalar()
        ) or 0  # Default to 0 if no transactions exist
        # Get balance at end of the year
        sats_end = (
            db.session.query(
                db.func.sum(
                    db.case(
                        (Transaction.type.in_(["buy", "earn"]), Transaction.sats),
                        (Transaction.type.in_(["sell", "spend"]), -Transaction.sats),
                        else_=0
                    )
                )
            )
            .filter(Transaction.datetime <= end_date, Transaction.user_id == current_user.id)
            .scalar()
        ) or 0  # Default to 0 if no transactions exist

        # Get BTC price at start and end of the year (we might need to fetch this from an API or manually store it)
        btc_price_start = get_btc_price(tax_year, "start")  # Function to fetch BTC price
        btc_price_end = get_btc_price(tax_year, "end")

        # Portfolio values
        portfolio_start = sats_start * Decimal(btc_price_start) / Decimal(1e8)
        portfolio_end = sats_end * Decimal(btc_price_end) / Decimal(1e8)

        # Sats bought and sold
        sats_bought = sum(tx.sats for tx in Transaction.query.filter(
            Transaction.type == "buy",
            Transaction.datetime >= start_date,
            Transaction.datetime <= end_date,
            Transaction.user_id == current_user.id
        ).all())
        sats_earned = sum(tx.sats for tx in Transaction.query.filter(
            Transaction.type == "earn",
            Transaction.datetime >= start_date,
            Transaction.datetime <= end_date,
            Transaction.user_id == current_user.id,
            (Transaction.notes == None) | (~Transaction.notes.like("%transfer%")) & (~Transaction.notes.like("%Transfer%"))  # Exclude "transfer" in notes (case-insensitive)
        ).all())
        sats_sold = sum(tx.sats for tx in Transaction.query.filter(
            Transaction.type == "sell",
            Transaction.datetime >= start_date,
            Transaction.datetime <= end_date,
            Transaction.user_id == current_user.id
        ).all())
        sats_spent = sum(tx.sats for tx in Transaction.query.filter(
            Transaction.type == "spend",
            Transaction.datetime >= start_date,
            Transaction.datetime <= end_date,
            Transaction.user_id == current_user.id,
            (Transaction.notes == None) | (~Transaction.notes.like("%transfer%")) & (~Transaction.notes.like("%Transfer%"))  # Exclude "transfer" in notes (case-insensitive)
        ).all())

        # Check for zero values to prevent division by zero
        if portfolio_end == Decimal(0):
            unrealized_gain_percent = Decimal(0)
            unrealized_gain_fiat = Decimal(0)
        
        elif portfolio_start == Decimal(0):
            # Unrealized Gain/Loss calculation
            first_year_of_buying = True
            transactions = Transaction.query.filter(
                Transaction.user_id == current_user.id,
                Transaction.type.in_(['buy', 'earn']),
                Transaction.datetime >= datetime(tax_year, 1, 1),
                Transaction.datetime <= datetime(tax_year, 12, 31),
                Transaction.fiat_amount > 0  # Prevent division by zero
            ).all()

            # Compute average manually
            if transactions:
                avg_sats_per_fiat = sum(tx.sats / tx.fiat_amount for tx in transactions) / len(transactions)
                avg_sats = sum(tx.sats for tx in transactions) / len(transactions)
            else:
                avg_sats_per_fiat = Decimal(0)
            unrealized_gain_percent = (Decimal(avg_sats_per_fiat) / ((Decimal(sats_end) / portfolio_end)) - 1) * Decimal(100)
            unrealized_gain_fiat = ((sats_bought + sats_earned) - (sats_sold + sats_spent)) / Decimal(avg_sats_per_fiat) * unrealized_gain_percent / Decimal(100)
        
        else:
            # Unrealized Gain/Loss calculation
            unrealized_gain_percent = ((Decimal(sats_start) / portfolio_start) / (Decimal(sats_end) / portfolio_end) - 1) * Decimal(100)
            unrealized_gain_fiat = portfolio_start + (portfolio_start * unrealized_gain_percent / Decimal(100))

        return {
            "sats_start": sats_start,
            "sats_end": sats_end,
            "btc_price_start": btc_price_start,
            "btc_price_end": btc_price_end,
            "first_year": first_year_of_buying,
            "portfolio_start": portfolio_start.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            "portfolio_end": portfolio_end.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            "sats_bought": sats_bought,
            "sats_earned": sats_earned,
            "sats_sold": sats_sold,
            "sats_spent": sats_spent,
            "unrealized_gain_percent": unrealized_gain_percent.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            "unrealized_gain_fiat": unrealized_gain_fiat.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        }

def get_btc_price(tax_year, date_type):
    # Ensure date_type is either "start" or "end"
    if date_type not in ["start", "end"]:
        raise ValueError("Invalid date_type. Must be 'start' or 'end'.")
    
    # Determine the date based on the date_type (start or end of tax year)
    if date_type == "start":
        target_date = datetime(tax_year, 1, 1)  # 01-Jan of the given tax year
    elif date_type == "end":
        target_date = datetime(tax_year, 12, 31)  # 31-Dec of the given tax year
    
    # Get the user's selected fiat currency
    currency = current_user.selected_fiat  # Get the fiat currency from the current_user
    
    # Define the API endpoint and parameters
    url = f"https://min-api.cryptocompare.com/data/v2/histoday"
    
    # Convert target_date to timestamp for the API query
    target_timestamp = int(target_date.timestamp())
    
    params = {
        'fsym': 'BTC',  # The symbol for Bitcoin
        'tsym': currency,  # The target currency (e.g., USD, EUR, etc.)
        'limit': 2000,  # Limit to the last 2000 days of data
        'toTs': target_timestamp,  # Use the target date timestamp as 'to' parameter
    }
    
    try:
        # Make the request to fetch historical Bitcoin prices
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        # Parse the JSON data from the response
        data = response.json()
        
        if data['Response'] == 'Error':
            raise ValueError("Error fetching BTC price data: " + data.get('Message', 'Unknown error'))
        
        # Extract the prices for the selected date
        prices = data['Data']['Data']
        
        # Find the Bitcoin price at the target date
        price_at_target_date = None
        for price in prices:
            if price['time'] >= target_timestamp:
                price_at_target_date = price['close']
                break
        
        if price_at_target_date is None:
            raise ValueError(f"Price data for {date_type} of {tax_year} could not be found")
        
        # Return the price
        return price_at_target_date

    except requests.exceptions.RequestException as e:
        print(f"Error fetching Bitcoin price data: {e}")
        return None
    except ValueError as e:
        print(e)
        return None
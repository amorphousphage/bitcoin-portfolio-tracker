from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail

# Initialize extensions (not linking to app yet)
db = SQLAlchemy()
mail = Mail()

def create_app():
    app = Flask(__name__, template_folder="templates")

    # Database Configuration
    app.config["SQLALCHEMY_DATABASE_URI"] = 'mysql+pymysql://username:password@bitcointracker_db_container/database'
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config['SECRET_KEY'] = 'your_secret_key'
    app.config['MAIL_SERVER'] = 'mail.yourdomain.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_SSL'] = False
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'mail@yourdomain.com'
    app.config['MAIL_PASSWORD'] = 'youremailpassword'
    app.config['MAIL_DEFAULT_SENDER'] = 'mail@yourdomain.com'

    # Initialize the db with the Flask app
    db.init_app(app)

    # Initialize Mail
    mail.init_app(app)

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.login_view = "main.login"
    login_manager.login_message_category = "info"
    login_manager.init_app(app)
    
    # Define the user_loader function
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id)) 

    # Create database tables if they don't exist
    from app import models

    with app.app_context():
        db.create_all()

    # Register Blueprints
    from app.routes import bp
    app.register_blueprint(bp)

    return app

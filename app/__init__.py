# app/__init__.py
from flask import Flask

app = Flask(__name__)
app.config.from_object('app.config')

from app.main.routes import main_bp
from app.company.routes import company_bp
from app.fiscal.routes import fiscal_bp
from app.dp.routes import dp_bp
from app.dashboard.routes import dashboard_bp 

app.register_blueprint(main_bp)
app.register_blueprint(company_bp)
app.register_blueprint(fiscal_bp)
app.register_blueprint(dp_bp)
app.register_blueprint(dashboard_bp)
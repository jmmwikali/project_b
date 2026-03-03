"""
================================================================
AGROVET BUSINESS MANAGEMENT SYSTEM — Flask Backend
Updated for PostgreSQL (Render free hosting)
================================================================
Run:  python app.py
API:  http://localhost:5000/api/...
================================================================
"""

from flask import Flask, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime
from functools import wraps
from dotenv import load_dotenv
import os

load_dotenv()

# ============================================================
# APP CONFIG
# ============================================================
app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')

# PostgreSQL connection (Render sets DATABASE_URL automatically)
db_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/agrovet_db')
# Render sometimes gives "postgres://" — SQLAlchemy needs "postgresql://"
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True   # required for cross-origin cookies

db = SQLAlchemy(app)

# Allow requests from your GitHub Pages frontend
allowed_origins = os.environ.get(
    'FRONTEND_ORIGINS',
    'http://localhost:3000,https://jmmwikali.github.io'
).split(',')

CORS(app, supports_credentials=True, origins=allowed_origins)


# ============================================================
# MODELS
# ============================================================

class User(db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name          = db.Column(db.String(100), nullable=False)
    role          = db.Column(db.String(20), nullable=False, default='attendant')  # 'admin' or 'attendant'
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    def to_dict(self):
        return {'id': self.id, 'username': self.username, 'name': self.name, 'role': self.role}


class Category(db.Model):
    __tablename__ = 'categories'
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    def to_dict(self):
        return {'id': self.id, 'name': self.name}


class Item(db.Model):
    __tablename__ = 'items'
    id               = db.Column(db.Integer, primary_key=True)
    name             = db.Column(db.String(150), nullable=False)
    category         = db.Column(db.String(100), nullable=False)
    cost_price       = db.Column(db.Numeric(12, 2), nullable=False)
    selling_price    = db.Column(db.Numeric(12, 2), nullable=False)
    quantity         = db.Column(db.Integer, nullable=False, default=0)
    min_stock_level  = db.Column(db.Integer, nullable=False, default=5)
    supplier_name    = db.Column(db.String(100))
    supplier_contact = db.Column(db.String(30))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sale_items = db.relationship('SaleItem', backref='item', lazy=True)
    movements  = db.relationship('StockMovement', backref='item', lazy=True)

    @property
    def profit_per_unit(self):
        return round(float(self.selling_price) - float(self.cost_price), 2)

    @property
    def profit_margin_pct(self):
        sp = float(self.selling_price)
        if sp == 0:
            return 0.0
        return round((self.profit_per_unit / sp) * 100, 2)

    @property
    def stock_status(self):
        if self.quantity == 0:
            return 'out_of_stock'
        if self.quantity <= self.min_stock_level:
            return 'low_stock'
        return 'in_stock'

    def to_dict(self):
        return {
            'id':                self.id,
            'name':              self.name,
            'category':          self.category,
            'cost_price':        float(self.cost_price),
            'selling_price':     float(self.selling_price),
            'quantity':          self.quantity,
            'min_stock_level':   self.min_stock_level,
            'supplier_name':     self.supplier_name,
            'supplier_contact':  self.supplier_contact,
            'profit_per_unit':   self.profit_per_unit,
            'profit_margin_pct': self.profit_margin_pct,
            'stock_status':      self.stock_status,
            'is_low_stock':      self.quantity <= self.min_stock_level,
        }


class Sale(db.Model):
    __tablename__ = 'sales'
    id           = db.Column(db.Integer, primary_key=True)
    date         = db.Column(db.Date, nullable=False, default=date.today)
    total_amount = db.Column(db.Numeric(14, 2), nullable=False)
    total_profit = db.Column(db.Numeric(14, 2), nullable=False)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    sale_items   = db.relationship('SaleItem', backref='sale', cascade='all, delete-orphan', lazy=True)

    def to_dict(self):
        return {
            'id':           self.id,
            'date':         str(self.date),
            'total_amount': float(self.total_amount),
            'total_profit': float(self.total_profit),
            'user_id':      self.user_id,
            'items':        [si.to_dict() for si in self.sale_items],
        }


class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id       = db.Column(db.Integer, primary_key=True)
    sale_id  = db.Column(db.Integer, db.ForeignKey('sales.id',  ondelete='CASCADE'),  nullable=False)
    item_id  = db.Column(db.Integer, db.ForeignKey('items.id',  ondelete='RESTRICT'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price    = db.Column(db.Numeric(12, 2), nullable=False)
    cost     = db.Column(db.Numeric(12, 2), nullable=False)
    profit   = db.Column(db.Numeric(12, 2), nullable=False)

    def to_dict(self):
        item_name = self.item.name if self.item else f'Item #{self.item_id}'
        return {
            'id':       self.id,
            'sale_id':  self.sale_id,
            'item_id':  self.item_id,
            'name':     item_name,
            'quantity': self.quantity,
            'price':    float(self.price),
            'cost':     float(self.cost),
            'profit':   float(self.profit),
            'total':    float(self.price) * self.quantity,
        }


class Expense(db.Model):
    __tablename__ = 'expenses'
    id          = db.Column(db.Integer, primary_key=True)
    date        = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount      = db.Column(db.Numeric(12, 2), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':          self.id,
            'date':        str(self.date),
            'description': self.description,
            'amount':      float(self.amount),
        }


class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id              = db.Column(db.Integer, primary_key=True)
    item_id         = db.Column(db.Integer, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False)
    movement_type   = db.Column(db.String(20), nullable=False)  # sale | restock | adjustment | opening
    quantity_change = db.Column(db.Integer, nullable=False)
    reason          = db.Column(db.String(100))
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':              self.id,
            'item_id':         self.item_id,
            'movement_type':   self.movement_type,
            'quantity_change': self.quantity_change,
            'reason':          self.reason,
            'created_at':      str(self.created_at),
        }


# ============================================================
# BUSINESS LOGIC
# ============================================================

def calc_line_profit(selling_price, cost_price, quantity):
    """total_profit = (selling_price - cost_price) * quantity"""
    return round((selling_price - cost_price) * quantity, 2)


def calc_net_profit(gross_profit, total_expenses):
    """net_profit = gross_profit - total_expenses"""
    return round(gross_profit - total_expenses, 2)


def log_movement(item_id, movement_type, qty_change, reason=None, user_id=None):
    db.session.add(StockMovement(
        item_id=item_id, movement_type=movement_type,
        quantity_change=qty_change, reason=reason, user_id=user_id
    ))


# ============================================================
# AUTH DECORATORS
# ============================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        user = db.session.get(User, session['user_id'])
        if not user or user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def current_uid():
    return session.get('user_id')


def err(msg, code=400):
    return jsonify({'error': msg}), code


def ok(data, code=200):
    return jsonify(data), code


# ============================================================
# AUTH ROUTES
# ============================================================

@app.route('/api/auth/login', methods=['POST'])
def login():
    d = request.get_json() or {}
    user = User.query.filter_by(username=d.get('username', '').strip()).first()
    if not user or not user.check_password(d.get('password', '')):
        return err('Invalid username or password', 401)
    session.permanent = True
    session['user_id'] = user.id
    return ok({'message': 'Login successful', 'user': user.to_dict()})


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return ok({'message': 'Logged out'})


@app.route('/api/auth/me', methods=['GET'])
@login_required
def me():
    return ok({'user': db.session.get(User, current_uid()).to_dict()})


@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def change_password():
    d    = request.get_json() or {}
    user = db.session.get(User, current_uid())
    if not user.check_password(d.get('current_password', '')):
        return err('Current password is incorrect', 403)
    user.set_password(d.get('new_password', ''))
    db.session.commit()
    return ok({'message': 'Password updated'})


# ============================================================
# INVENTORY ROUTES
# ============================================================

@app.route('/api/items', methods=['GET'])
@login_required
def get_items():
    category = request.args.get('category')
    status   = request.args.get('status')
    search   = request.args.get('q', '').strip()

    q = Item.query
    if category:
        q = q.filter_by(category=category)
    if search:
        q = q.filter(Item.name.ilike(f'%{search}%'))
    items = q.order_by(Item.name).all()

    if status:
        items = [i for i in items if i.stock_status == status]

    alerts = [
        {'id': i.id, 'name': i.name, 'quantity': i.quantity,
         'min': i.min_stock_level, 'status': i.stock_status}
        for i in items if i.quantity <= i.min_stock_level
    ]
    return ok({'items': [i.to_dict() for i in items], 'low_stock_alerts': alerts})


@app.route('/api/items/<int:item_id>', methods=['GET'])
@login_required
def get_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return err('Item not found', 404)
    return ok({'item': item.to_dict()})


@app.route('/api/items', methods=['POST'])
@admin_required
def create_item():
    d = request.get_json() or {}
    for f in ['name', 'category', 'cost_price', 'selling_price', 'quantity', 'min_stock_level']:
        if f not in d:
            return err(f'Missing field: {f}')
    if float(d['quantity']) < 0:
        return err('Quantity cannot be negative')

    item = Item(
        name=d['name'].strip(), category=d['category'],
        cost_price=float(d['cost_price']), selling_price=float(d['selling_price']),
        quantity=int(d['quantity']), min_stock_level=int(d['min_stock_level']),
        supplier_name=d.get('supplier_name'), supplier_contact=d.get('supplier_contact'),
    )
    db.session.add(item)
    db.session.flush()
    if item.quantity > 0:
        log_movement(item.id, 'opening', item.quantity, 'Initial stock', current_uid())
    db.session.commit()
    return ok({'item': item.to_dict(), 'message': 'Item created'}, 201)


@app.route('/api/items/<int:item_id>', methods=['PUT'])
@admin_required
def update_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return err('Item not found', 404)
    d = request.get_json() or {}
    for f in ['name', 'category', 'cost_price', 'selling_price', 'min_stock_level',
              'supplier_name', 'supplier_contact']:
        if f in d:
            setattr(item, f, d[f])
    db.session.commit()
    return ok({'item': item.to_dict(), 'message': 'Item updated'})


@app.route('/api/items/<int:item_id>', methods=['DELETE'])
@admin_required
def delete_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return err('Item not found', 404)
    if item.sale_items:
        return err('Cannot delete item with sales history. Reduce quantity to 0 instead.', 409)
    db.session.delete(item)
    db.session.commit()
    return ok({'message': f'"{item.name}" deleted'})


@app.route('/api/items/<int:item_id>/restock', methods=['POST'])
@login_required
def restock_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return err('Item not found', 404)
    d   = request.get_json() or {}
    qty = int(d.get('quantity', 0))
    if qty <= 0:
        return err('Quantity must be greater than 0')
    item.quantity += qty
    log_movement(item.id, 'restock', qty, d.get('reason', 'Restock'), current_uid())
    db.session.commit()
    return ok({'item': item.to_dict(), 'message': f'Restocked {qty} units. New total: {item.quantity}'})


@app.route('/api/items/<int:item_id>/adjust', methods=['POST'])
@admin_required
def adjust_stock(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return err('Item not found', 404)
    d      = request.get_json() or {}
    qty    = int(d.get('quantity', 0))
    reason = d.get('reason', 'Manual adjustment')
    if qty <= 0:
        return err('Quantity must be greater than 0')
    if qty > item.quantity:
        return err(f'Cannot reduce by {qty}: only {item.quantity} in stock')
    item.quantity -= qty
    log_movement(item.id, 'adjustment', -qty, reason, current_uid())
    db.session.commit()
    return ok({'item': item.to_dict(), 'message': f'Stock reduced by {qty}. Remaining: {item.quantity}'})


# ============================================================
# SALES ROUTES
# ============================================================

@app.route('/api/sales', methods=['GET'])
@login_required
def get_sales():
    month     = request.args.get('month')
    date_from = request.args.get('date_from')
    date_to   = request.args.get('date_to')

    q = Sale.query
    if month:
        year, mon = map(int, month.split('-'))
        q = q.filter(
            db.extract('year',  Sale.date) == year,
            db.extract('month', Sale.date) == mon,
        )
    else:
        if date_from:
            q = q.filter(Sale.date >= date_from)
        if date_to:
            q = q.filter(Sale.date <= date_to)

    sales = q.order_by(Sale.date.desc()).all()
    return ok({
        'sales': [s.to_dict() for s in sales],
        'summary': {
            'total_revenue':      sum(float(s.total_amount) for s in sales),
            'total_profit':       sum(float(s.total_profit) for s in sales),
            'total_transactions': len(sales),
        }
    })


@app.route('/api/sales', methods=['POST'])
@login_required
def create_sale():
    d    = request.get_json() or {}
    cart = d.get('items', [])
    if not cart:
        return err('Cart is empty')

    total_amount = 0.0
    total_profit = 0.0
    resolved     = []

    # Validate everything before touching the DB
    for ci in cart:
        item = db.session.get(Item, ci.get('item_id'))
        if not item:
            return err(f'Item ID {ci.get("item_id")} not found', 404)
        qty = int(ci.get('quantity', 0))
        if qty <= 0:
            return err(f'Invalid quantity for "{item.name}"')
        if item.quantity < qty:
            return err(f'Insufficient stock for "{item.name}": {item.quantity} available, {qty} requested')

        line_profit   = calc_line_profit(float(item.selling_price), float(item.cost_price), qty)
        total_amount += float(item.selling_price) * qty
        total_profit += line_profit
        resolved.append({'item': item, 'qty': qty, 'line_profit': line_profit})

    # Commit atomically
    sale = Sale(date=date.today(), total_amount=round(total_amount, 2),
                total_profit=round(total_profit, 2), user_id=current_uid())
    db.session.add(sale)
    db.session.flush()

    for r in resolved:
        item = r['item']
        db.session.add(SaleItem(
            sale_id=sale.id, item_id=item.id, quantity=r['qty'],
            price=float(item.selling_price), cost=float(item.cost_price),
            profit=r['line_profit'],
        ))
        item.quantity -= r['qty']
        log_movement(item.id, 'sale', -r['qty'], f'Sale #{sale.id}', current_uid())

    db.session.commit()
    return ok({'sale': sale.to_dict(), 'receipt': _build_receipt(sale),
               'message': f'Sale recorded. Total: KES {total_amount:,.2f}'}, 201)


def _build_receipt(sale):
    seller = db.session.get(User, sale.user_id)
    return {
        'receipt_number': f'RCP-{sale.id:06d}',
        'date':     str(sale.date),
        'time':     datetime.utcnow().strftime('%H:%M:%S'),
        'cashier':  seller.name if seller else 'Unknown',
        'items': [{
            'name':       si.item.name if si.item else f'Item #{si.item_id}',
            'quantity':   si.quantity,
            'unit_price': float(si.price),
            'total':      float(si.price) * si.quantity,
        } for si in sale.sale_items],
        'total': float(sale.total_amount),
    }


@app.route('/api/sales/<int:sale_id>/receipt', methods=['GET'])
@login_required
def get_receipt(sale_id):
    sale = db.session.get(Sale, sale_id)
    if not sale:
        return err('Sale not found', 404)
    return ok({'receipt': _build_receipt(sale)})


# ============================================================
# EXPENSES ROUTES
# ============================================================

@app.route('/api/expenses', methods=['GET'])
@admin_required
def get_expenses():
    month = request.args.get('month')
    q = Expense.query
    if month:
        year, mon = map(int, month.split('-'))
        q = q.filter(
            db.extract('year',  Expense.date) == year,
            db.extract('month', Expense.date) == mon,
        )
    expenses = q.order_by(Expense.date.desc()).all()
    return ok({'expenses': [e.to_dict() for e in expenses],
               'total': sum(float(e.amount) for e in expenses)})


@app.route('/api/expenses', methods=['POST'])
@admin_required
def create_expense():
    d = request.get_json() or {}
    if not d.get('description') or not d.get('amount'):
        return err('description and amount are required')
    if float(d['amount']) <= 0:
        return err('Amount must be greater than 0')
    exp = Expense(date=d.get('date', date.today()),
                  description=d['description'].strip(),
                  amount=float(d['amount']), user_id=current_uid())
    db.session.add(exp)
    db.session.commit()
    return ok({'expense': exp.to_dict(), 'message': 'Expense recorded'}, 201)


@app.route('/api/expenses/<int:expense_id>', methods=['DELETE'])
@admin_required
def delete_expense(expense_id):
    exp = db.session.get(Expense, expense_id)
    if not exp:
        return err('Expense not found', 404)
    db.session.delete(exp)
    db.session.commit()
    return ok({'message': 'Expense deleted'})


# ============================================================
# REPORTS ROUTES
# ============================================================

@app.route('/api/reports/monthly', methods=['GET'])
@admin_required
def monthly_report():
    month     = request.args.get('month', date.today().strftime('%Y-%m'))
    year, mon = map(int, month.split('-'))

    sales    = Sale.query.filter(
        db.extract('year',  Sale.date) == year,
        db.extract('month', Sale.date) == mon,
    ).all()
    expenses = Expense.query.filter(
        db.extract('year',  Expense.date) == year,
        db.extract('month', Expense.date) == mon,
    ).all()

    total_revenue  = sum(float(s.total_amount) for s in sales)
    total_profit   = sum(float(s.total_profit) for s in sales)
    total_expenses = sum(float(e.amount) for e in expenses)
    net_profit     = calc_net_profit(total_profit, total_expenses)
    items_sold     = sum(si.quantity for s in sales for si in s.sale_items)

    # Movement counts
    movement = {}
    for s in sales:
        for si in s.sale_items:
            name = si.item.name if si.item else f'Item #{si.item_id}'
            movement[name] = movement.get(name, 0) + si.quantity

    sorted_m    = sorted(movement.items(), key=lambda x: x[1], reverse=True)
    fast_moving = [{'name': k, 'units_sold': v} for k, v in sorted_m[:5]]
    slow_moving = [{'name': k, 'units_sold': v} for k, v in sorted_m[-5:][::-1]]
    out_of_stock = [i.to_dict() for i in Item.query.filter_by(quantity=0).all()]

    # Stock loss detection
    discrepancies = []
    for item in Item.query.all():
        sold = movement.get(item.name, 0)
        if sold == 0:
            continue
        restocked = db.session.query(
            db.func.coalesce(db.func.sum(StockMovement.quantity_change), 0)
        ).filter(
            StockMovement.item_id == item.id,
            StockMovement.movement_type == 'restock',
            db.extract('year',  StockMovement.created_at) == year,
            db.extract('month', StockMovement.created_at) == mon,
        ).scalar()

        adjusted = db.session.query(
            db.func.coalesce(db.func.sum(StockMovement.quantity_change), 0)
        ).filter(
            StockMovement.item_id == item.id,
            StockMovement.movement_type == 'adjustment',
            db.extract('year',  StockMovement.created_at) == year,
            db.extract('month', StockMovement.created_at) == mon,
        ).scalar()

        opening_stock    = item.quantity + sold - restocked - adjusted
        expected_closing = opening_stock - sold + restocked + adjusted
        discrepancy      = item.quantity - expected_closing

        if discrepancy != 0:
            discrepancies.append({
                'item_id':          item.id,
                'item_name':        item.name,
                'opening_stock':    opening_stock,
                'sold':             sold,
                'restocked':        restocked,
                'adjusted':         abs(adjusted),
                'expected_closing': expected_closing,
                'actual_closing':   item.quantity,
                'discrepancy':      discrepancy,
                'flag':             'potential_loss' if discrepancy < 0 else 'unexplained_gain',
            })

    return ok({
        'month': month,
        'financial_summary': {
            'total_revenue':      total_revenue,
            'total_profit':       total_profit,
            'total_expenses':     total_expenses,
            'net_profit':         net_profit,
            'total_items_sold':   items_sold,
            'total_transactions': len(sales),
            'profit_margin_pct':  round(total_profit / total_revenue * 100, 2) if total_revenue > 0 else 0,
        },
        'inventory_movement': {
            'fast_moving':  fast_moving,
            'slow_moving':  slow_moving,
            'out_of_stock': out_of_stock,
        },
        'stock_loss_detection': {
            'discrepancies_found': len(discrepancies),
            'items':               discrepancies,
        },
        'expenses_detail': [e.to_dict() for e in expenses],
    })


@app.route('/api/reports/today', methods=['GET'])
@login_required
def today_summary():
    sales = Sale.query.filter_by(date=date.today()).all()
    return ok({
        'date':               str(date.today()),
        'total_revenue':      sum(float(s.total_amount) for s in sales),
        'total_profit':       sum(float(s.total_profit) for s in sales),
        'total_transactions': len(sales),
        'sales':              [s.to_dict() for s in sales],
    })


@app.route('/api/reports/stock-movements', methods=['GET'])
@admin_required
def stock_movements_route():
    item_id = request.args.get('item_id', type=int)
    q = StockMovement.query
    if item_id:
        q = q.filter_by(item_id=item_id)
    movements = q.order_by(StockMovement.created_at.desc()).limit(200).all()
    return ok({'movements': [m.to_dict() for m in movements]})


# ============================================================
# DASHBOARD
# ============================================================

@app.route('/api/dashboard', methods=['GET'])
@login_required
def dashboard():
    all_items    = Item.query.all()
    all_sales    = Sale.query.all()
    all_expenses = Expense.query.all()

    total_revenue  = sum(float(s.total_amount) for s in all_sales)
    total_profit   = sum(float(s.total_profit) for s in all_sales)
    total_expenses = sum(float(e.amount) for e in all_expenses)

    today_sales   = [s for s in all_sales if s.date == date.today()]
    today_revenue = sum(float(s.total_amount) for s in today_sales)
    today_profit  = sum(float(s.total_profit) for s in today_sales)

    item_sold_map = {}
    for s in all_sales:
        for si in s.sale_items:
            name = si.item.name if si.item else f'Item #{si.item_id}'
            item_sold_map[name] = item_sold_map.get(name, 0) + si.quantity
    top_items = sorted(item_sold_map.items(), key=lambda x: x[1], reverse=True)[:5]

    return ok({
        'inventory_stats': {
            'total_products':     len(all_items),
            'total_units':        sum(i.quantity for i in all_items),
            'low_stock_count':    sum(1 for i in all_items if i.stock_status in ('low_stock', 'out_of_stock')),
            'out_of_stock_count': sum(1 for i in all_items if i.stock_status == 'out_of_stock'),
            'low_stock_items':    [i.to_dict() for i in all_items if i.stock_status in ('low_stock', 'out_of_stock')],
        },
        'financial_stats': {
            'total_revenue':  total_revenue,
            'total_profit':   total_profit,
            'total_expenses': total_expenses,
            'net_profit':     calc_net_profit(total_profit, total_expenses),
            'today_revenue':  today_revenue,
            'today_profit':   today_profit,
        },
        'top_items':    [{'name': k, 'units_sold': v} for k, v in top_items],
        'recent_sales': [s.to_dict() for s in Sale.query.order_by(Sale.date.desc()).limit(5).all()],
    })


# ============================================================
# USERS (admin only)
# ============================================================

@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    return ok({'users': [u.to_dict() for u in User.query.order_by(User.name).all()]})


@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    d = request.get_json() or {}
    for f in ['username', 'password', 'name', 'role']:
        if not d.get(f):
            return err(f'Missing field: {f}')
    if User.query.filter_by(username=d['username']).first():
        return err('Username already exists', 409)
    user = User(username=d['username'].strip(), name=d['name'].strip(), role=d['role'])
    user.set_password(d['password'])
    db.session.add(user)
    db.session.commit()
    return ok({'user': user.to_dict(), 'message': 'User created'}, 201)


@app.route('/api/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return err('User not found', 404)
    d = request.get_json() or {}
    if 'name' in d:
        user.name = d['name'].strip()
    if 'role' in d:
        user.role = d['role']
    if d.get('password'):
        user.set_password(d['password'])
    db.session.commit()
    return ok({'user': user.to_dict(), 'message': 'User updated'})


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    if user_id == current_uid():
        return err('You cannot delete your own account', 403)
    user = db.session.get(User, user_id)
    if not user:
        return err('User not found', 404)
    db.session.delete(user)
    db.session.commit()
    return ok({'message': f'User "{user.username}" deleted'})


# ============================================================
# CATEGORIES
# ============================================================

@app.route('/api/categories', methods=['GET'])
@login_required
def get_categories():
    return ok({'categories': [c.to_dict() for c in Category.query.order_by(Category.name).all()]})


@app.route('/api/categories', methods=['POST'])
@admin_required
def create_category():
    d = request.get_json() or {}
    name = d.get('name', '').strip()
    if not name:
        return err('Category name is required')
    if Category.query.filter_by(name=name).first():
        return err('Category already exists', 409)
    cat = Category(name=name)
    db.session.add(cat)
    db.session.commit()
    return ok({'category': cat.to_dict()}, 201)


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'error': 'Method not allowed'}), 405


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================
# SEED
# ============================================================

def seed_database():
    for name in ['Animal Feeds', 'Farm Tools', 'Medicines']:
        if not Category.query.filter_by(name=name).first():
            db.session.add(Category(name=name))
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', name='Admin User', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        print('Default admin created  →  admin / admin123')
        print('IMPORTANT: Change this password after first login!')
    db.session.commit()


# ============================================================
# ENTRY POINT
# ============================================================

# ── Run on every startup (works with both gunicorn and python app.py) ──
with app.app_context():
    db.create_all()
    seed_database()

if __name__ == '__main__':
    print('Agrovet API running at http://localhost:5000')
    app.run(
        debug=os.environ.get('FLASK_DEBUG', 'true').lower() == 'true',
        port=5000
    )



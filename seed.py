"""
seed.py — Load sample data for testing.
Run after tables are created:  python seed.py
"""
from app import app, db, User, Category, Item, Sale, SaleItem, Expense, log_movement
from datetime import date, timedelta

def seed():
    with app.app_context():
        db.create_all()
        print("Seeding...")

        # Categories
        for name in ['Animal Feeds', 'Farm Tools', 'Medicines']:
            if not Category.query.filter_by(name=name).first():
                db.session.add(Category(name=name))
        db.session.commit()

        # Users
        users_data = [
            {'username': 'admin',          'name': 'Admin User',   'role': 'admin',     'password': 'admin123'},
            {'username': 'jane_attendant', 'name': 'Jane Wanjiku', 'role': 'attendant', 'password': 'jane123'},
        ]
        for ud in users_data:
            if not User.query.filter_by(username=ud['username']).first():
                u = User(username=ud['username'], name=ud['name'], role=ud['role'])
                u.set_password(ud['password'])
                db.session.add(u)
        db.session.commit()

        admin = User.query.filter_by(username='admin').first()
        jane  = User.query.filter_by(username='jane_attendant').first()

        # Inventory
        items_data = [
            {'name': 'Broiler Starter Mash (50kg)', 'category': 'Animal Feeds',  'cost_price': 2200, 'selling_price': 2600, 'quantity': 45, 'min_stock_level': 10, 'supplier_name': 'Unga Feeds Ltd',   'supplier_contact': '0712345678'},
            {'name': 'Layer Mash (50kg)',            'category': 'Animal Feeds',  'cost_price': 2100, 'selling_price': 2450, 'quantity': 30, 'min_stock_level': 10, 'supplier_name': 'Unga Feeds Ltd',   'supplier_contact': '0712345678'},
            {'name': 'Dairy Meal (50kg)',            'category': 'Animal Feeds',  'cost_price': 1800, 'selling_price': 2200, 'quantity':  3, 'min_stock_level':  5, 'supplier_name': 'Farmfeed Co',      'supplier_contact': '0723456789'},
            {'name': 'Hand Hoe (Jembe)',             'category': 'Farm Tools',    'cost_price':  350, 'selling_price':  480, 'quantity': 25, 'min_stock_level':  8, 'supplier_name': 'Agritools Kenya', 'supplier_contact': '0734567890'},
            {'name': 'Garden Fork',                  'category': 'Farm Tools',    'cost_price':  580, 'selling_price':  750, 'quantity': 12, 'min_stock_level':  5, 'supplier_name': 'Agritools Kenya', 'supplier_contact': '0734567890'},
            {'name': 'Knapsack Sprayer (16L)',        'category': 'Farm Tools',    'cost_price': 2800, 'selling_price': 3500, 'quantity':  2, 'min_stock_level':  3, 'supplier_name': 'Agritools Kenya', 'supplier_contact': '0734567890'},
            {'name': 'Drenching Gun',                'category': 'Medicines',     'cost_price': 1200, 'selling_price': 1600, 'quantity':  8, 'min_stock_level':  3, 'supplier_name': 'Vet Supplies EA',  'supplier_contact': '0745678901'},
            {'name': 'Oxytetracycline 100ml',        'category': 'Medicines',     'cost_price':  380, 'selling_price':  520, 'quantity':  0, 'min_stock_level':  5, 'supplier_name': 'Vet Supplies EA',  'supplier_contact': '0745678901'},
            {'name': 'Ivermectin Injection 50ml',    'category': 'Medicines',     'cost_price':  650, 'selling_price':  900, 'quantity': 15, 'min_stock_level':  5, 'supplier_name': 'Vet Supplies EA',  'supplier_contact': '0745678901'},
            {'name': 'Cattle Dewormer (Albendazole)','category': 'Medicines',     'cost_price':  450, 'selling_price':  650, 'quantity': 20, 'min_stock_level':  6, 'supplier_name': 'Vet Supplies EA',  'supplier_contact': '0745678901'},
        ]

        created_items = {}
        for idata in items_data:
            item = Item.query.filter_by(name=idata['name']).first()
            if not item:
                item = Item(**idata)
                db.session.add(item)
                db.session.flush()
                if item.quantity > 0:
                    log_movement(item.id, 'opening', item.quantity, 'Initial stock', admin.id)
            created_items[idata['name']] = item
        db.session.commit()

        # Sales (Feb 2025)
        base = date(2025, 2, 1)
        sales_data = [
            {'date': base,                 'user': admin, 'items': [('Broiler Starter Mash (50kg)', 2)]},
            {'date': base + timedelta(2),  'user': admin, 'items': [('Hand Hoe (Jembe)', 3), ('Ivermectin Injection 50ml', 4)]},
            {'date': base + timedelta(4),  'user': admin, 'items': [('Broiler Starter Mash (50kg)', 1)]},
            {'date': base + timedelta(6),  'user': jane,  'items': [('Layer Mash (50kg)', 3), ('Cattle Dewormer (Albendazole)', 3)]},
            {'date': base + timedelta(9),  'user': admin, 'items': [('Knapsack Sprayer (16L)', 1)]},
            {'date': base + timedelta(13), 'user': jane,  'items': [('Drenching Gun', 1), ('Ivermectin Injection 50ml', 4), ('Hand Hoe (Jembe)', 4)]},
            {'date': base + timedelta(17), 'user': admin, 'items': [('Layer Mash (50kg)', 2)]},
            {'date': base + timedelta(19), 'user': admin, 'items': [('Garden Fork', 2), ('Cattle Dewormer (Albendazole)', 2)]},
        ]

        for sd in sales_data:
            if Sale.query.filter_by(date=sd['date'], user_id=sd['user'].id).first():
                continue
            total_amount = total_profit = 0.0
            lines = []
            for item_name, qty in sd['items']:
                item = created_items.get(item_name)
                if not item: continue
                price  = float(item.selling_price)
                cost   = float(item.cost_price)
                profit = (price - cost) * qty
                total_amount += price * qty
                total_profit += profit
                lines.append({'item': item, 'qty': qty, 'price': price, 'cost': cost, 'profit': profit})

            sale = Sale(date=sd['date'], total_amount=round(total_amount,2),
                        total_profit=round(total_profit,2), user_id=sd['user'].id)
            db.session.add(sale)
            db.session.flush()
            for li in lines:
                db.session.add(SaleItem(sale_id=sale.id, item_id=li['item'].id,
                    quantity=li['qty'], price=li['price'], cost=li['cost'], profit=li['profit']))
                log_movement(li['item'].id, 'sale', -li['qty'], f'Sale #{sale.id}', sd['user'].id)
        db.session.commit()

        # Expenses (Feb 2025)
        for ed in [
            {'date': base,                 'desc': 'Shop rent',              'amount': 8000},
            {'date': base + timedelta(2),  'desc': 'Electricity bill',       'amount': 1200},
            {'date': base + timedelta(9),  'desc': 'Employee salary - Jane', 'amount': 12000},
            {'date': base + timedelta(14), 'desc': 'Cleaning supplies',      'amount': 450},
            {'date': base + timedelta(19), 'desc': 'Internet bill',          'amount': 800},
        ]:
            if not Expense.query.filter_by(date=ed['date'], description=ed['desc']).first():
                db.session.add(Expense(date=ed['date'], description=ed['desc'],
                                       amount=ed['amount'], user_id=admin.id))
        db.session.commit()

        print("Done! Login: admin/admin123  or  jane_attendant/jane123")

if __name__ == '__main__':
    seed()




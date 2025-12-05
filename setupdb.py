from app import db, app

print("Running db.create_all() for database initialization...")
with app.app_context():
    db.create_all()
    print("Database tables successfully created.")
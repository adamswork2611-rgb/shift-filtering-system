from flask import Flask, request, render_template, send_file, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO
from filter import get_excel, filter_shift

app = Flask(__name__)
app.config['SECRET_KEY'] = 'iy"a*r8+6J_X""4'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("You do not have permission to access this page.", 'error')
            return redirect(url_for('upload_file'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user:
            flash('Email address already exists.')
            return redirect(url_for('signup'))
        
        is_first_user = User.query.count() == 0

        new_user = User(
            email=email, 
            is_approved=is_first_user,
            is_admin=is_first_user
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        if is_first_user:
            flash("Account created! You are the first user (Admin) and automatically approved. Please log in.")
            return redirect(url_for('login'))
        else:
            flash('Account created! An admin must approve your account before you can log in.')
            return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Invalid email or password.')
            return redirect(url_for('login'))

        if not user.is_approved:
            flash('Your account has not yet been approved by an admin.')
            return redirect(url_for('login'))

        login_user(user)
        return redirect(url_for('upload_file'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin/manage_users', methods=['GET', 'POST'])
@login_required 
@admin_required

def manage_users():
    pending_users = User.query.filter_by(is_approved=False, is_admin=False).all()
    approved_users = User.query.filter_by(is_approved=True).all()

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        action = request.form.get('action')

        user_to_act = User.query.get(user_id)
        if user_to_act:
            if action == 'approve':
                user_to_act.is_approved = True
                db.session.commit()
                flash(f'User {user_to_act.email} has been approved.', 'success')
            elif action == 'delete':
                if user_to_act.id != current_user.id:
                    db.session.delete(user_to_act)
                    db.session.commit()
                    flash(f'User {user_to_act.email} has been deleted.', 'success')
                else:
                    flash("You cannot delete your own admin account.", 'error')
        
        return redirect(url_for('manage_users'))
    
    return render_template(
        'manage_users.html', 
        pending_users=pending_users, 
        approved_users=approved_users
    )


@app.route('/', methods=['GET', 'POST'])
@login_required 
def upload_file():
    if request.method == 'POST':
        output_files = request.files.getlist('files')
        combined_df = get_excel(output_files)
        filtered_df = filter_shift(combined_df)
        output = BytesIO()
        filtered_df.to_excel(output, index=False)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='filtered_shift_data.xlsx'
        )

    return render_template('index.html', user_email=current_user.email, is_admin=current_user.is_admin)


if __name__ == '__main__':
    with app.app_context():
        db.create_all() 
    app.run(debug=True)
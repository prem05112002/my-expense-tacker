
from flask import Flask, jsonify, request
from models import db, User
from worker import MailWorker
from dbsetup import bootstrap_database # <--- Import the new function

# 1. Run Setup & Get Connection String
db_uri = bootstrap_database() 

app = Flask(__name__)

# 2. Use the generated URI
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
worker = MailWorker(app)

@app.route('/connect', methods=['POST'])
def connect_bank():
    data = request.json
    
    # Check if user exists, else create
    user = User.query.filter_by(email=data['email']).first()
    if not user:
        user = User(
            email=data['email'],
            imap_server="imap.gmail.com",
            imap_user=data['email'],
            imap_password=data['password'] 
        )
        db.session.add(user)
        db.session.commit()

    worker.start_onboarding(user)
    return jsonify({"status": "Onboarding started..."})

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Creates tables inside the new DB
    app.run(debug=True, port=5000)
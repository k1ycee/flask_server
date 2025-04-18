from flask import Flask, request, jsonify, make_response, render_template, redirect
from config import Config
from database import db, User, Message
from socket_events import socketio
from functools import wraps
import jwt
from datetime import datetime, timedelta

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize Flask-SQLAlchemy
    db.init_app(app)
    
    # Initialize Socket.IO
    socketio.init_app(app, cors_allowed_origins="*")
    
    # Create tables within app context
    with app.app_context():
        db.create_all()

    # Add login page route
    @app.route('/login')
    def login_page():
        return render_template('login.html')

    # Add root route that redirects to login if not authenticated
    @app.route('/')
    def index():
        return redirect('/login')

    def token_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None
            
            if 'Authorization' in request.headers:
                token = request.headers['Authorization'].split(" ")[1]
            
            if not token:
                return jsonify({'message': 'Token is missing'}), 401
            
            try:
                data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
                current_user = User.find_by_public_id(data['public_id'])
            except:
                return jsonify({'message': 'Token is invalid'}), 401
            
            return f(current_user, *args, **kwargs)
        return decorated

    @app.route('/auth/signup', methods=['POST'])
    def signup():
        data = request.get_json()
        
        # Check if required fields are present
        if not all(k in data for k in ['username', 'email', 'password']):
            return jsonify({'message': 'Missing required fields'}), 400
        
        # Check if user already exists
        if User.find_by_username(data['username']):
            return jsonify({'message': 'Username already exists'}), 409
        
        if User.find_by_email(data['email']):
            return jsonify({'message': 'Email already exists'}), 409
        
        try:
            # Create new user
            new_user = User.create_user(
                username=data['username'],
                email=data['email'],
                password=data['password']
            )
            
            # Add user to database
            db.session.add(new_user)
            db.session.commit()
            
            return jsonify({
                'message': 'User created successfully',
                'user': {
                    'public_id': new_user.public_id,
                    'username': new_user.username,
                    'email': new_user.email
                }
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': 'Error creating user', 'error': str(e)}), 500

    @app.route('/auth/signin', methods=['POST'])
    def signin():
        auth = request.get_json()
        
        if not auth or not auth.get('username') or not auth.get('password'):
            return jsonify({'message': 'Missing authentication details'}), 400
        
        # Find user by username
        user = User.find_by_username(auth.get('username'))
        
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        # Check password
        if user.verify_password(auth.get('password')):
            # Generate token
            token = jwt.encode({
                'public_id': user.public_id,
                'exp': datetime.utcnow() + timedelta(hours=24)
            }, app.config['SECRET_KEY'], algorithm="HS256")
            
            return jsonify({
                'token': token,
                'user': {
                    'public_id': user.public_id,
                    'username': user.username,
                    'email': user.email
                }
            }), 200
        
        return jsonify({'message': 'Invalid password'}), 401

    @app.route('/auth/user', methods=['GET'])
    @token_required
    def get_user(current_user):
        return jsonify({
            'user': {
                'public_id': current_user.public_id,
                'username': current_user.username,
                'email': current_user.email
            }
        }), 200

    # Add a new route to get user conversations
    @app.route('/conversations/<username>', methods=['GET'])
    @token_required
    def get_conversation(current_user, username):
        other_user = User.find_by_username(username)
        if not other_user:
            return jsonify({'message': 'User not found'}), 404
        
        messages = Message.get_conversation(current_user.id, other_user.id)
        conversation = [{
            'id': msg.id,
            'content': msg.content,
            'sender_username': msg.sender.username,
            'receiver_username': msg.receiver.username,
            'created_at': msg.created_at.isoformat()
        } for msg in messages]
        
        return jsonify({'messages': conversation}), 200

    @app.route('/chat')
    def chat_page():
        return render_template('chat.html')

    return app

if __name__ == '__main__':
    app = create_app()
    socketio.run(app, debug=True)

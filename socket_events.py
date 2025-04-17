from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request
from database import db, Message, User
import jwt
from config import Config

socketio = SocketIO()

def get_user_from_token(token):
    try:
        data = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
        return User.find_by_public_id(data['public_id'])
    except:
        return None

@socketio.on('connect')
def handle_connect():
    token = request.args.get('token')
    if not token:
        return False
    
    user = get_user_from_token(token)
    if not user:
        return False
    
    # Join user's personal room
    join_room(f"user_{user.id}")
    return True

@socketio.on('send_message')
def handle_message(data):
    token = request.args.get('token')
    user = get_user_from_token(token)
    if not user:
        return False
    
    receiver = User.find_by_username(data['receiver_username'])
    if not receiver:
        emit('error', {'message': 'Receiver not found'})
        return
    
    # Create and save the message
    message = Message()
    message.sender_id = user.id
    message.receiver_id = receiver.id
    message.content = data['message']  # This will automatically encrypt
    
    db.session.add(message)
    db.session.commit()
    
    # Emit to both sender and receiver
    message_data = {
        'id': message.id,
        'content': message.content,  # This will automatically decrypt
        'sender_username': user.username,
        'receiver_username': receiver.username,
        'created_at': message.created_at.isoformat()
    }
    
    emit('new_message', message_data, room=f"user_{user.id}")
    emit('new_message', message_data, room=f"user_{receiver.id}")

@socketio.on('get_conversation')
def handle_get_conversation(data):
    token = request.args.get('token')
    user = get_user_from_token(token)
    if not user:
        return False
    
    other_user = User.find_by_username(data['username'])
    if not other_user:
        emit('error', {'message': 'User not found'})
        return
    
    messages = Message.get_conversation(user.id, other_user.id)
    conversation = [{
        'id': msg.id,
        'content': msg.content,
        'sender_username': msg.sender.username,
        'receiver_username': msg.receiver.username,
        'created_at': msg.created_at.isoformat()
    } for msg in messages]
    
    emit('conversation_history', {'messages': conversation})
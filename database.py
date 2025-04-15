from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    white_games = db.relationship('Game', backref='white_player', foreign_keys='Game.white_player_id', lazy=True)
    black_games = db.relationship('Game', backref='black_player', foreign_keys='Game.black_player_id', lazy=True)

    @property
    def password(self):
        """Prevent password from being accessed"""
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        """Set password to a hashed password"""
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        """Check if hashed password matches actual password"""
        return check_password_hash(self.password_hash, password)

    @classmethod
    def create_user(cls, username, email, password):
        """Create a new user"""
        user = cls(
            username=username,
            email=email
        )
        user.password = password  # This will hash the password
        return user

    @hybrid_property
    def all_games(self):
        """Returns all games where user is either white or black player"""
        return self.white_games + self.black_games

    @classmethod
    def find_by_username(cls, username):
        return cls.query.filter_by(username=username).first()

    @classmethod
    def find_by_email(cls, email):
        return cls.query.filter_by(email=email).first()

    @classmethod
    def find_by_public_id(cls, public_id):
        return cls.query.filter_by(public_id=public_id).first()

    def get_active_games(self):
        """Returns all ongoing games for the user"""
        return Game.query.filter(
            or_(
                Game.white_player_id == self.id,
                Game.black_player_id == self.id
            ),
            Game.status == 'ongoing'
        ).all()

    def __repr__(self):
        return f"<User {self.username}>"

class Game(db.Model):
    __tablename__ = 'games'
    
    id = db.Column(db.Integer, primary_key=True)
    white_player_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    black_player_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    current_turn = db.Column(db.String(5), default='white')  # 'white' or 'black'
    fen = db.Column(db.Text, nullable=False, default='rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')  # standard starting position
    move_list = db.Column(db.PickleType, default=list)  # list of SAN moves
    status = db.Column(db.String(20), default='ongoing')  # ongoing, finished, etc.
    result = db.Column(db.String(7), nullable=True)  # 1-0, 0-1, 1/2-1/2

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def current_player_id(self):
        """Returns the ID of the player whose turn it is"""
        return self.white_player_id if self.current_turn == 'white' else self.black_player_id

    @property
    def is_finished(self):
        """Returns whether the game is finished"""
        return self.status != 'ongoing'

    @classmethod
    def get_active_games(cls):
        """Returns all ongoing games"""
        return cls.query.filter_by(status='ongoing').all()

    @classmethod
    def find_by_id(cls, game_id):
        """Find a game by its ID"""
        return cls.query.get(game_id)

    def add_move(self, move):
        """Add a move to the game's move list"""
        if self.move_list is None:
            self.move_list = []
        self.move_list.append(move)
        # Toggle the current turn
        self.current_turn = 'black' if self.current_turn == 'white' else 'white'

    def end_game(self, result):
        """End the game with a specific result"""
        self.status = 'finished'
        self.result = result

    def __repr__(self):
        return f"<Game {self.id} - {self.white_player.username} vs {self.black_player.username}>"

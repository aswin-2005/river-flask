from flask import Flask, jsonify, request
from flask_cors import CORS
import random
import string 
import os
from supabase import create_client, Client
from dotenv import load_dotenv
from collections import deque

# Load environment variables from .env file
load_dotenv()

class UserCache:
    def __init__(self, max_size=10):
        self.max_size = max_size
        self.cache = deque(maxlen=max_size)
    
    def add_user(self, username: str, token: str):
        # Remove if user already exists in cache
        self.remove_user(username)
        # Add new user data
        self.cache.append({"username": username, "token": token})
    
    def remove_user(self, username: str):
        self.cache = deque([user for user in self.cache if user["username"] != username], maxlen=self.max_size)
    
    def get_user(self, username: str):
        for user in self.cache:
            if user["username"] == username:
                return user
        return None
    
    def check_user_validity(self, username: str, token: str):
        user = self.get_user(username)
        if user and user["token"] == token:
            return True
        return False

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)
user_cache = UserCache()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

def read_users():
    try:
        response = supabase.table('users').select("*").execute()
        users = {}
        for user in response.data:
            users[user['username']] = user['token']
        return users
    except Exception as e:
        print(f"Error reading users: {str(e)}")
        return {}

def write_user(username, token):
    try:
        supabase.table('users').insert({"username": username, "token": token}).execute()
        user_cache.add_user(username, token)
    except Exception as e:
        raise Exception(f"Failed to write user: {str(e)}")

def remove_user(username):
    try:
        response = supabase.table('users').delete().eq('username', username).execute()
        user_cache.remove_user(username)
        return len(response.data) > 0
    except Exception as e:
        print(f"Error removing user: {str(e)}")
        return False

def tokenGenerator():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

def checkUserValidity(username: str, token: str):
    # First check in cache
    if user_cache.check_user_validity(username, token):
        return True
        
    # If not in cache, check in database
    try:
        response = supabase.table('users').select("*").eq('username', username).eq('token', token).execute()
        is_valid = len(response.data) > 0
        if is_valid:
            # Add to cache if found in database
            user_cache.add_user(username, token)
        return is_valid
    except Exception as e:
        print(f"Error checking user validity: {str(e)}")
        return False

# Basic error handling
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

#i think i need to remove it later as it serve no purpose to fn as an api. the function is only used in the socket server.
@app.route('/validate-token', methods=['POST'])
def validate_token():
    token = request.json.get('token')
    username = request.json.get('username')
    if checkUserValidity(username, token):
        return jsonify({'userExists': True}), 200
    else:
        return jsonify({'userExists': False}), 404

@app.route('/login', methods=['POST'])
def login():
    try:
        # Get and validate username
        username = request.json.get('username')
        if not username or not isinstance(username, str) or len(username.strip()) == 0:
            return jsonify({'error': 'Invalid username'}), 400
        username = username.strip()
        
        # Check if user exists
        users = read_users()
        if username in users:
            return jsonify({
                'message': 'Username already exists',
                'userExists': True
            }), 400
        
        # Generate token and create new user
        token = tokenGenerator()
        try:
            write_user(username, token)
            return jsonify({
                'message': 'User created successfully',
                'userExists': False,
                'token': token,
                'username': username
            }), 201
        except Exception as e:
            return jsonify({
                'error': 'Failed to create user',
                'details': str(e)
            }), 500
    except Exception as e:
        return jsonify({
            'error': 'Server error',
            'details': str(e)
        }), 500
    

@app.route('/logout', methods=['POST'])
def logout():
    username = request.json.get('username')
    if not username or not isinstance(username, str) or len(username.strip()) == 0:
        return jsonify({'error': 'Invalid username'}), 400
    username = username.strip()
    remove_user(username)
    return jsonify({'message': 'User logged out successfully'}), 200

@app.route('/cleanup', methods=['POST'])
def cleanup():
    try:
        # Get the list of active users from the socket server
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
            
        active_users = request.json.get('active_users', [])  # Default to empty list if not provided
        
        # Validate input is a list
        if not isinstance(active_users, list):
            return jsonify({'error': 'active_users must be a list'}), 400
            
        # Get all current users from database
        response = supabase.table('users').select("*").execute()
        current_users = response.data
        
        # Find users to remove (users in DB but not in active_users list)
        removed_count = 0
        if len(active_users) > 0:
            for user in current_users:
                if user['username'] not in active_users:
                    if remove_user(user['username']):
                        removed_count += 1
        else:
            # If active_users is empty, remove all users
            for user in current_users:
                if remove_user(user['username']):
                    removed_count += 1
                    
        return jsonify({
            'message': 'Cleanup completed successfully',
            'removed_count': removed_count
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Server error during cleanup',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

from flask import Flask, jsonify, request
from flask_cors import CORS
import random
import string 
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

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
    except Exception as e:
        raise Exception(f"Failed to write user: {str(e)}")

def remove_user(username):
    try:
        response = supabase.table('users').delete().eq('username', username).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error removing user: {str(e)}")
        return False

def tokenGenerator():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

def checkUserValidity(username: str, token: str):
    try:
        response = supabase.table('users').select("*").eq('username', username).eq('token', token).execute()
        return len(response.data) > 0
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
        active_users = request.json.get('active_users')
        
        # Validate input
        if not active_users or not isinstance(active_users, list):
            return jsonify({'error': 'Invalid active users list'}), 400
            
        # Get all current users from database
        response = supabase.table('users').select("*").execute()
        current_users = response.data
        
        # Find users to remove (users in DB but not in active_users list)
        removed_count = 0
        for user in current_users:
            if user['username'] not in active_users:
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

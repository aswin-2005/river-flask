from flask import Flask, jsonify, request
from flask_cors import CORS
import random
import string 
import csv
import os


app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# CSV file path
USERS_CSV = 'users.csv'

# Create CSV file if it doesn't exist
def init_csv():
    if not os.path.exists(USERS_CSV):
        with open(USERS_CSV, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['username', 'token'])

# Function to read users from CSV
def read_users():
    users = {}
    with open(USERS_CSV, 'r', newline='') as file:
        reader = csv.DictReader(file)
        for row in reader:
            users[row['username']] = row['token']
    return users

# Function to write user to CSV
def write_user(username, token):
    users = read_users()
    users[username] = token
    with open(USERS_CSV, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['username', 'token'])
        for username, token in users.items():
            writer.writerow([username, token])

# Function to remove user from CSV
def remove_user(username):
    users = read_users()
    if username in users:
        del users[username]
        with open(USERS_CSV, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['username', 'token'])
            for username, token in users.items():
                writer.writerow([username, token])
        return True
    return False

def tokenGenerator():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

def checkUserValidity(username: str, token: str):
    users = read_users()
    return username in users and users[username] == token


# Initialize CSV file
init_csv()

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

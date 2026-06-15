
from collections import OrderedDict

import binascii

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

import hashlib
import json
import os
import threading
from time import time, sleep
from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS



MINING_SENDER = "THE BLOCKCHAIN"
MINING_REWARD = 1
MINING_DIFFICULTY = 2
FAUCET_REWARD = 100

# Port is parsed early so each node gets its own data file
from argparse import ArgumentParser as _AP
_parser = _AP()
_parser.add_argument('-p', '--port', default=5000, type=int)
_args, _ = _parser.parse_known_args()
BLOCKCHAIN_DATA_FILE = f'blockchain_{_args.port}.json'


class Blockchain:

    def __init__(self):
        
        self.transactions = []
        self.chain = []
        self.nodes = set()
        self.node_id = str(uuid4()).replace('-', '')
        self.mining = False
        self.stop_mining = False
        self.mining_thread = None

        if not self.load_from_file():
            self.create_block(0, '00')

        # Auto sync with peers on startup in background
        if self.nodes:
            sync_thread = threading.Thread(target=self.startup_sync, daemon=True)
            sync_thread.start()


    def startup_sync(self):
        """
        Auto sync with peers on startup.
        Waits for Flask server to be ready then syncs chain.
        """
        sleep(3)  # Wait for Flask server to start
        print("Startup sync: contacting peers...")
        replaced = self.resolve_conflicts()
        if replaced:
            print("Startup sync: chain updated from peer")
        else:
            print("Startup sync: chain is up to date")

    def register_node(self, node_url):
        """
        Add a new node to the list of nodes
        """
        #Checking node_url has valid format
        parsed_url = urlparse(node_url)
        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc)
        elif parsed_url.path:
            # Accepts an URL without scheme like '192.168.0.5:5000'.
            self.nodes.add(parsed_url.path)
        else:
            raise ValueError('Invalid URL')
        
        # Save after registering node
        self.save_to_file()


    def verify_transaction_signature(self, sender_address, signature, transaction):
        """
        Verify transaction signature using ECC public key (secp256k1)
        """
        try:
            public_key = serialization.load_der_public_key(
                binascii.unhexlify(sender_address),
                backend=default_backend()
            )
            message = str(transaction).encode('utf8')
            public_key.verify(
                binascii.unhexlify(signature),
                message,
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except InvalidSignature:
            return False
        except Exception:
            return False


    def get_pending_spent(self, address):
        """
        Calculate total amount already spent in pending (unconfirmed) transactions
        """
        pending_spent = 0
        for tx in self.transactions:
            if tx['sender_address'] == address:
                pending_spent += float(tx['value'])
        return pending_spent

    def is_double_spend(self, sender_address, value):
        """
        Check if sender has enough balance considering pending transactions
        Returns True if double spend detected
        """
        balance_info = self.get_wallet_balance(sender_address)
        confirmed_balance = balance_info['balance']
        pending_spent = self.get_pending_spent(sender_address)
        available_balance = confirmed_balance - pending_spent
        return float(value) > available_balance

    def submit_transaction(self, sender_address, recipient_address, value, signature):
        """
        Add a transaction to transactions array if the signature verified
        """
        transaction = OrderedDict({'sender_address': sender_address, 
                                    'recipient_address': recipient_address,
                                    'value': value})

        # Reward for mining a block - skip validation
        if sender_address == MINING_SENDER or sender_address == 'FAUCET':
            self.transactions.append(transaction)
            self.save_to_file()
            return len(self.chain) + 1

        # Validate amount is positive
        if float(value) <= 0:
            return 'invalid_amount'

        # Verify signature
        transaction_verification = self.verify_transaction_signature(sender_address, signature, transaction)
        if not transaction_verification:
            return 'invalid_signature'

        # Check balance and double spending
        if self.is_double_spend(sender_address, value):
            return 'insufficient_balance'

        self.transactions.append(transaction)
        self.save_to_file()
        self.broadcast_transaction(transaction)
        return len(self.chain) + 1


    def create_block(self, nonce, previous_hash):
        """
        Add a block of transactions to the blockchain
        """
        block = {'block_number': len(self.chain) + 1,
                'timestamp': time(),
                'transactions': self.transactions,
                'nonce': nonce,
                'previous_hash': previous_hash}

        # Reset the current list of transactions
        self.transactions = []

        self.chain.append(block)
        self.save_to_file()
        return block


    def hash(self, block):
        """
        Create a SHA-256 hash of a block
        """
        # We must make sure that the Dictionary is Ordered, or we'll have inconsistent hashes
        block_string = json.dumps(block, sort_keys=True).encode()
        
        return hashlib.sha256(block_string).hexdigest()


    def proof_of_work(self):
        """
        Proof of work algorithm - supports stop signal for competitive mining
        """
        last_block = self.chain[-1]
        last_hash = self.hash(last_block)

        nonce = 0
        while self.valid_proof(self.transactions, last_hash, nonce) is False:
            # Check stop signal - another node found block first
            if self.stop_mining:
                return None
            nonce += 1

        return nonce

    def auto_mine(self):
        """
        Background mining loop - continuously mines blocks when transactions exist
        """
        print(f"Auto mining started on node {self.node_id[:8]}...")
        while self.mining:
            # Only mine if there are pending transactions
            if len(self.transactions) > 0:
                print(f"Auto mining: {len(self.transactions)} pending transactions found, starting mining...")
                self.stop_mining = False

                last_block = self.chain[-1]
                nonce = self.proof_of_work()

                # If stop signal received, another node won - skip
                if nonce is None:
                    print("Auto mining: stopped - another node mined first")
                    sleep(1)
                    continue

                # Add mining reward
                self.submit_transaction(
                    sender_address=MINING_SENDER,
                    recipient_address=self.node_id,
                    value=MINING_REWARD,
                    signature=""
                )

                # Create and broadcast block
                previous_hash = self.hash(last_block)
                block = self.create_block(nonce, previous_hash)
                self.broadcast_block(block)
                print(f"Auto mining: Block {block['block_number']} mined and broadcasted!")
            else:
                # No transactions, wait before checking again
                sleep(3)

    def start_auto_mining(self):
        """
        Start background mining thread
        """
        if not self.mining:
            self.mining = True
            self.stop_mining = False
            self.mining_thread = threading.Thread(target=self.auto_mine, daemon=True)
            self.mining_thread.start()
            print("Auto mining thread started")

    def stop_auto_mining(self):
        """
        Stop background mining thread
        """
        self.mining = False
        self.stop_mining = True
        print("Auto mining stopped")


    def valid_proof(self, transactions, last_hash, nonce, difficulty=MINING_DIFFICULTY):
        """
        Check if a hash value satisfies the mining conditions. This function is used within the proof_of_work function.
        """
        guess = (str(transactions)+str(last_hash)+str(nonce)).encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:difficulty] == '0'*difficulty


    def valid_chain(self, chain):
        """
        check if a bockchain is valid
        """
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            #print(last_block)
            #print(block)
            #print("\n-----------\n")
            # Check that the hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Check that the Proof of Work is correct
            #Delete the reward transaction
            transactions = block['transactions'][:-1]
            # Need to make sure that the dictionary is ordered. Otherwise we'll get a different hash
            transaction_elements = ['sender_address', 'recipient_address', 'value']
            transactions = [OrderedDict((k, transaction[k]) for k in transaction_elements) for transaction in transactions]

            if not self.valid_proof(transactions, block['previous_hash'], block['nonce'], MINING_DIFFICULTY):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        Resolve conflicts between blockchain's nodes
        by replacing our chain with the longest one in the network.
        """
        neighbours = self.nodes
        new_chain = None

        # We're only looking for chains longer than ours
        max_length = len(self.chain)

        # Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            print('http://' + node + '/chain')
            response = requests.get('http://' + node + '/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            self.chain = new_chain
            self.save_to_file()
            return True

        return False

    def save_to_file(self):
        """
        Save blockchain data to file
        """
        data = {
            'chain': self.chain,
            'transactions': self.transactions,
            'nodes': list(self.nodes),
            'node_id': self.node_id
        }
        try:
            with open(BLOCKCHAIN_DATA_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving blockchain data: {e}")

    def load_from_file(self):
        """
        Load blockchain data from file
        Returns True if data loaded successfully, False otherwise
        """
        if not os.path.exists(BLOCKCHAIN_DATA_FILE):
            return False
        
        try:
            with open(BLOCKCHAIN_DATA_FILE, 'r') as f:
                data = json.load(f)
            
            self.chain = data.get('chain', [])
            self.transactions = data.get('transactions', [])
            self.nodes = set(data.get('nodes', []))
            self.node_id = data.get('node_id', self.node_id)
            
            print(f"Blockchain data loaded: {len(self.chain)} blocks, {len(self.transactions)} pending transactions")
            return True
        except Exception as e:
            print(f"Error loading blockchain data: {e}")
            return False

    def get_wallet_balance(self, address):
        """
        Calculate wallet balance including pending transactions
        """
        balance = 0
        total_received = 0
        total_sent = 0

        # Confirmed balance from mined blocks
        for block in self.chain[1:]:
            for transaction in block['transactions']:
                if transaction['recipient_address'] == address:
                    amount = float(transaction['value'])
                    balance += amount
                    total_received += amount
                if transaction['sender_address'] == address:
                    amount = float(transaction['value'])
                    balance -= amount
                    total_sent += amount

        # Also include pending received transactions in balance
        for transaction in self.transactions:
            if transaction['recipient_address'] == address:
                amount = float(transaction['value'])
                balance += amount
                total_received += amount

        return {
            'balance': balance,
            'total_received': total_received,
            'total_sent': total_sent
        }

    def broadcast_transaction(self, transaction):
        """
        Broadcast new transaction to all registered nodes
        """
        for node in self.nodes:
            try:
                url = f'http://{node}/transactions/receive'
                requests.post(url, json={
                    'sender_address': transaction['sender_address'],
                    'recipient_address': transaction['recipient_address'],
                    'value': transaction['value']
                }, timeout=2)
                print(f"Transaction broadcasted to {node}")
            except Exception as e:
                print(f"Failed to broadcast transaction to {node}: {e}")

    def broadcast_block(self, block):
        """
        Broadcast newly mined block to all registered nodes
        """
        for node in self.nodes:
            try:
                url = f'http://{node}/block/receive'
                requests.post(url, json={'block': block}, timeout=2)
                print(f"Block broadcasted to {node}")
            except Exception as e:
                print(f"Failed to broadcast to {node}: {e}")

    def receive_block(self, block):
        """
        Receive and validate a block from another node.
        Stop current mining since peer won this round.
        """
        if block['block_number'] == len(self.chain) + 1:
            if block['previous_hash'] == self.hash(self.chain[-1]):
                # Stop current mining - peer won this round
                self.stop_mining = True
                self.chain.append(block)
                # Clear transactions that are now confirmed in this block
                confirmed = {(tx['sender_address'], tx['recipient_address'], str(tx['value']))
                             for tx in block['transactions']}
                self.transactions = [
                    tx for tx in self.transactions
                    if (tx['sender_address'], tx['recipient_address'], str(tx['value'])) not in confirmed
                ]
                self.save_to_file()
                print(f"Block {block['block_number']} received from peer - mining reset")
                return True
        return False

# Instantiate the Node
app = Flask(__name__)
CORS(app)

# Instantiate the Blockchain
blockchain = Blockchain()

@app.route('/')
def index():
    return render_template('./index.html')

@app.route('/configure')
def configure():
    return render_template('./configure.html')



@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.form

    required = ['sender_address', 'recipient_address', 'amount', 'signature']
    if not all(k in values for k in required):
        return 'Missing values', 400

    transaction_result = blockchain.submit_transaction(values['sender_address'], values['recipient_address'], values['amount'], values['signature'])

    if transaction_result == 'invalid_signature':
        return jsonify({'message': 'Invalid Transaction! Signature verification failed.'}), 406
    elif transaction_result == 'insufficient_balance':
        return jsonify({'message': 'Invalid Transaction! Insufficient balance or double spending detected.'}), 406
    elif transaction_result == 'invalid_amount':
        return jsonify({'message': 'Invalid Transaction! Amount must be greater than 0.'}), 406
    else:
        return jsonify({'message': 'Transaction will be added to Block ' + str(transaction_result)}), 201

@app.route('/transactions/get', methods=['GET'])
def get_transactions():
    #Get transactions from transactions pool
    transactions = blockchain.transactions

    response = {'transactions': transactions}
    return jsonify(response), 200

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/mine', methods=['GET'])
def mine():
    # Manual mine - same as before but also resets stop signal
    blockchain.stop_mining = False
    last_block = blockchain.chain[-1]
    nonce = blockchain.proof_of_work()

    if nonce is None:
        return jsonify({'message': 'Mining interrupted - another node mined first'}), 200

    blockchain.submit_transaction(sender_address=MINING_SENDER, recipient_address=blockchain.node_id, value=MINING_REWARD, signature="")
    previous_hash = blockchain.hash(last_block)
    block = blockchain.create_block(nonce, previous_hash)
    blockchain.broadcast_block(block)

    response = {
        'message': "New Block Forged",
        'block_number': block['block_number'],
        'transactions': block['transactions'],
        'nonce': block['nonce'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200


@app.route('/mine/start', methods=['GET'])
def start_mining():
    if blockchain.mining:
        return jsonify({'message': 'Auto mining already running'}), 200
    blockchain.start_auto_mining()
    return jsonify({'message': 'Auto mining started - node will mine automatically when transactions exist'}), 200


@app.route('/mine/stop', methods=['GET'])
def stop_mining():
    blockchain.stop_auto_mining()
    return jsonify({'message': 'Auto mining stopped'}), 200


@app.route('/mine/status', methods=['GET'])
def mining_status():
    return jsonify({
        'auto_mining': blockchain.mining,
        'pending_transactions': len(blockchain.transactions)
    }), 200



@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.form
    nodes = values.get('nodes').replace(" ", "").split(',')

    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': [node for node in blockchain.nodes],
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }
    return jsonify(response), 200


@app.route('/nodes/get', methods=['GET'])
def get_nodes():
    nodes = list(blockchain.nodes)
    response = {'nodes': nodes}
    return jsonify(response), 200


@app.route('/wallet/balance', methods=['POST'])
def wallet_balance():
    values = request.form
    address = values.get('address')

    if not address:
        return 'Missing wallet address', 400

    balance_info = blockchain.get_wallet_balance(address)

    # Check if any pending transactions exist for this address
    has_pending = any(
        tx['recipient_address'] == address
        for tx in blockchain.transactions
    )

    response = {
        'address': address,
        'balance': balance_info['balance'],
        'total_received': balance_info['total_received'],
        'total_sent': balance_info['total_sent'],
        'has_pending': has_pending
    }
    return jsonify(response), 200


@app.route('/wallet/faucet', methods=['POST'])
def faucet():
    values = request.get_json()
    address = values.get('address')

    if not address:
        return jsonify({'message': 'Missing wallet address'}), 400

    # Check if this wallet already received faucet reward
    for block in blockchain.chain[1:]:
        for tx in block['transactions']:
            if tx['sender_address'] == 'FAUCET' and tx['recipient_address'] == address:
                return jsonify({'message': 'Faucet already claimed for this wallet'}), 406

    # Also check pending transactions
    for tx in blockchain.transactions:
        if tx['sender_address'] == 'FAUCET' and tx['recipient_address'] == address:
            return jsonify({'message': 'Faucet already claimed and pending for this wallet'}), 406

    # Add faucet reward transaction directly to pool
    transaction = OrderedDict({
        'sender_address': 'FAUCET',
        'recipient_address': address,
        'value': FAUCET_REWARD
    })
    blockchain.transactions.append(transaction)
    blockchain.save_to_file()
    print(f"Faucet reward of {FAUCET_REWARD} coins sent to {address[:20]}...")

    return jsonify({'message': f'Faucet reward of {FAUCET_REWARD} coins added! Mine a block to confirm.'}), 201


@app.route('/block/receive', methods=['POST'])
def receive_block():
    values = request.get_json()
    block = values.get('block')
    
    if not block:
        return 'Missing block data', 400
    
    if blockchain.receive_block(block):
        response = {'message': 'Block received and added'}
        return jsonify(response), 201
    else:
        response = {'message': 'Block rejected'}
        return jsonify(response), 400


@app.route('/transactions/receive', methods=['POST'])
def receive_transaction():
    """
    Receive a broadcasted transaction from another node
    """
    values = request.get_json()

    required = ['sender_address', 'recipient_address', 'value']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Check if transaction already exists in pool (avoid duplicates)
    for tx in blockchain.transactions:
        if (tx['sender_address'] == values['sender_address'] and
            tx['recipient_address'] == values['recipient_address'] and
            tx['value'] == values['value']):
            return jsonify({'message': 'Transaction already in pool'}), 200

    # Add directly to pool (already validated by sender node)
    transaction = OrderedDict({
        'sender_address': values['sender_address'],
        'recipient_address': values['recipient_address'],
        'value': values['value']
    })
    blockchain.transactions.append(transaction)
    blockchain.save_to_file()
    print(f"Transaction received from peer and added to pool")

    return jsonify({'message': 'Transaction added to pool'}), 201



if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    print(f"Starting node on port {port}")
    print(f"Data file: {BLOCKCHAIN_DATA_FILE}")

    app.run(host='127.0.0.1', port=port)









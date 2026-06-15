# Blockchain Project - Step by Step Testing Guide

---

## Prerequisites

Make sure you have installed all required dependencies before starting.

    pip install flask flask-cors requests cryptography pycryptodome

---

## Project Structure

    blockchain-project/
    |-- blockchain/
    |   |-- blockchain.py
    |   |-- templates/
    |   |   |-- index.html
    |   |   |-- configure.html
    |-- blockchain_client/
    |   |-- blockchain_client.py
    |   |-- templates/
    |   |   |-- index.html
    |   |   |-- make_transaction.html
    |   |   |-- view_transactions.html
    |   |   |-- check_balance.html

---

## Part 1: Basic Setup - Single Node

### Step 1: Start the Blockchain Node

Open Terminal 1 and run:

    cd c:\Users\rutwik\OneDrive\Desktop\blockchain-project\blockchain
    python blockchain.py -p 5000

You should see in the console:

    Starting node on port 5000
    Data file: blockchain_5000.json

This means node 5000 has started and created its own data file.

### Step 2: Start the Blockchain Client

Open Terminal 2 and run:

    cd c:\Users\rutwik\OneDrive\Desktop\blockchain-project\blockchain_client
    python blockchain_client.py -p 8080

You should see:

    Running on http://127.0.0.1:8080

### Step 3: Verify Both Are Running

Open your browser and check:

    http://127.0.0.1:5000   - Should show Blockchain Frontend page
    http://127.0.0.1:8080   - Should show Blockchain Client page

---

## Part 2: Wallet Generation and Faucet Reward

### Step 4: Generate a Wallet

1. Go to http://127.0.0.1:8080
2. Make sure the Blockchain Node URL field shows http://127.0.0.1:5000
3. Click the Generate Wallet button
4. You will see two text boxes fill up with keys

The Public Key is your wallet address. It is shorter than before because we now use ECC instead of RSA.
The Private Key is your password to send coins. Never share this.

5. You will see a green message saying 100 coins have been added as a welcome reward
6. Copy and save both keys somewhere. You will need them for transactions.

### Step 5: Verify Faucet Reward in Pending Pool

1. Go to http://127.0.0.1:5000
2. You should see the faucet transaction in the pending transactions table at the top
3. The sender will show FAUCET and the recipient will be your public key
4. The value will be 100

This means the faucet reward is waiting to be mined into a block.

### Step 6: Check Balance Before Mining

1. Go to http://127.0.0.1:8080
2. Click Check Balance in the navigation
3. Paste your Public Key in the Wallet Address field
4. Keep Node URL as http://127.0.0.1:5000
5. Click Check Balance

You should see:

    Available Balance: 100.00 coins
    Total Received: 100.00 coins (includes pending)
    Note: Some coins are pending. Mine a block to fully confirm them.

The balance shows 100 even before mining because pending received transactions are included.

### Step 7: Mine the Faucet Transaction

1. Go to http://127.0.0.1:5000
2. Click the Mine button
3. The page will reload
4. You should now see the faucet transaction in the Transactions on the Blockchain table at the bottom
5. The pending transactions table at the top should now be empty

### Step 8: Check Balance After Mining

1. Go to http://127.0.0.1:8080
2. Click Check Balance
3. Paste your Public Key
4. Click Check Balance

You should now see:

    Available Balance: 100.00 coins
    Total Received: 100.00 coins
    Total Sent: 0.00 coins

The pending note should be gone now because the coins are fully confirmed.

---

## Part 3: Making Transactions

### Step 9: Generate a Second Wallet

1. Go to http://127.0.0.1:8080
2. Click Generate Wallet again
3. Save the second wallet Public Key and Private Key separately
4. This will be the recipient wallet

Note: The second wallet also gets 100 coins faucet reward. Mine another block to confirm it.

### Step 10: Make a Transaction

1. Go to http://127.0.0.1:8080
2. Click Make Transaction in the navigation
3. Fill in the form:

    Sender Address:      Paste your first wallet Public Key
    Sender Private Key:  Paste your first wallet Private Key
    Recipient Address:   Paste your second wallet Public Key
    Amount to Send:      Enter 10

4. Click Generate Transaction
5. A popup will appear showing the transaction details and a digital signature
6. The Blockchain Node URL should show http://127.0.0.1:5000
7. Click Confirm Transaction

You should see a green success popup saying the transaction will be added to the next block.

### Step 11: Verify Transaction is Pending

1. Go to http://127.0.0.1:5000
2. You should see the transaction in the pending transactions table
3. Sender is your first wallet address
4. Recipient is your second wallet address
5. Value is 10

### Step 12: Mine the Transaction

1. On http://127.0.0.1:5000
2. Click Mine
3. Page reloads
4. Transaction moves from pending table to the blockchain table at the bottom

### Step 13: Verify Balances After Transaction

Check balance of first wallet:

    Available Balance: 90.00 coins
    Total Received: 100.00 coins
    Total Sent: 10.00 coins

Check balance of second wallet:

    Available Balance: 110.00 coins
    Total Received: 110.00 coins
    Total Sent: 0.00 coins

---

## Part 4: Testing Validation

### Step 14: Test Insufficient Balance

1. Go to Make Transaction
2. Try to send 200 coins from your first wallet which only has 90 coins
3. Click Generate Transaction then Confirm Transaction

You should see a red error popup:

    Transaction Failed!
    Invalid Transaction! Insufficient balance or double spending detected.

### Step 15: Test Invalid Amount

1. Go to Make Transaction
2. Enter 0 as the amount
3. Click Generate Transaction then Confirm Transaction

You should see:

    Transaction Failed!
    Invalid Transaction! Amount must be greater than 0.

### Step 16: Test Double Spending

1. Go to Make Transaction
2. Send 80 coins from first wallet (which has 90 coins)
3. Do NOT mine yet
4. Try to send another 80 coins from the same wallet
5. You should get insufficient balance error because 80 coins are already locked in pending

---

## Part 5: Testing Multiple Nodes

### Step 17: Start a Second Node

Open Terminal 3 and run:

    cd c:\Users\rutwik\OneDrive\Desktop\blockchain-project\blockchain
    python blockchain.py -p 5001

You should see:

    Starting node on port 5001
    Data file: blockchain_5001.json

Notice it creates blockchain_5001.json separately from blockchain_5000.json.

### Step 18: Verify Separate Data Files

Go to the blockchain folder and you should see:

    blockchain_5000.json   - Data for node 5000
    blockchain_5001.json   - Data for node 5001

Open both files and compare. They will have different node_id values and node 5001 will only have the genesis block since it just started.

### Step 19: Register Nodes With Each Other

On Node 5000 (http://127.0.0.1:5000):
1. Click Configure in the navigation
2. Enter 127.0.0.1:5001 in the Node URLs field
3. Click Add Node
4. You should see 127.0.0.1:5001 appear in the list below

On Node 5001 (http://127.0.0.1:5001):
1. Click Configure
2. Enter 127.0.0.1:5000 in the Node URLs field
3. Click Add Node
4. You should see 127.0.0.1:5000 appear in the list below

### Step 20: Test Transaction Broadcasting

1. Go to http://127.0.0.1:8080
2. Make a transaction and send it to http://127.0.0.1:5000
3. Go to http://127.0.0.1:5000 - you should see the pending transaction
4. Go to http://127.0.0.1:5001 - you should ALSO see the same pending transaction

This confirms transaction broadcasting is working. The transaction was automatically sent from node 5000 to node 5001.

### Step 21: Test Competitive Mining

1. Go to http://127.0.0.1:5000 and click Start Auto Mining
2. Go to http://127.0.0.1:5001 and click Start Auto Mining
3. Submit a transaction from the client
4. Watch the console logs in both terminals

You will see something like:

    Terminal 1 (Node 5000):
    Auto mining: 1 pending transactions found, starting mining...
    Auto mining: Block 2 mined and broadcasted!
    Block broadcasted to 127.0.0.1:5001

    Terminal 2 (Node 5001):
    Block 2 received from peer - mining reset

This means node 5000 won the mining race and node 5001 accepted the block.

### Step 22: Verify Both Nodes Have Same Chain

Check balance from node 5000:

    http://127.0.0.1:8080 - Check Balance - Node URL: http://127.0.0.1:5000

Check same wallet balance from node 5001:

    http://127.0.0.1:8080 - Check Balance - Node URL: http://127.0.0.1:5001

Both should show the exact same balance. This confirms both nodes have the same blockchain data.

### Step 23: View Transactions From Both Nodes

1. Go to http://127.0.0.1:8080
2. Click View Transactions
3. Enter http://127.0.0.1:5000 and click View Transactions
4. Note the transactions shown
5. Change to http://127.0.0.1:5001 and click View Transactions
6. Both should show identical transaction history

---

## Part 6: Testing Automatic Startup Sync

### Step 24: Stop Node 5001

Press Ctrl+C in Terminal 3 to stop node 5001.

### Step 25: Mine Some Blocks on Node 5000 While 5001 is Offline

1. Make 2 or 3 transactions from the client to node 5000
2. Mine each transaction on node 5000
3. Node 5001 is offline so it misses all these blocks

### Step 26: Restart Node 5001

In Terminal 3 run:

    python blockchain.py -p 5001

Watch the console output carefully. You should see:

    Starting node on port 5001
    Data file: blockchain_5001.json
    Blockchain data loaded: 1 blocks, 0 pending transactions
    Startup sync: contacting peers...
    http://127.0.0.1:5000/chain
    Startup sync: chain updated from peer

This means node 5001 automatically downloaded the missing blocks from node 5000 on startup.

### Step 27: Verify Node 5001 is Now in Sync

1. Go to http://127.0.0.1:5001
2. Check the Transactions on the Blockchain table
3. It should show all the transactions that were mined while it was offline
4. Check balance from node 5001 - should match node 5000

---

## Part 7: Checking the JSON Data Files

### Step 28: Compare the JSON Files

Open blockchain_5000.json and blockchain_5001.json in any text editor.

After syncing you should see:

    Both files have the same number of blocks in the chain array
    Both files have the same transactions inside each block
    Both files have different node_id values
    Both files may have different nodes arrays depending on registration

This confirms that:
- Each node has its own independent file
- But the chain data is identical after syncing
- node_id is always unique per node

---

## Part 8: Auto Mining Test

### Step 29: Test Auto Mining on Both Nodes

1. Go to http://127.0.0.1:5000 - Click Start Auto Mining - Badge shows Auto Mining: ON
2. Go to http://127.0.0.1:5001 - Click Start Auto Mining - Badge shows Auto Mining: ON
3. Submit multiple transactions from the client
4. Watch both node pages - the Pending count badge updates every 3 seconds
5. After a few seconds the transactions will be automatically mined without clicking Mine

### Step 30: Stop Auto Mining

1. Go to http://127.0.0.1:5000 - Click Stop Auto Mining - Badge shows Auto Mining: OFF
2. Go to http://127.0.0.1:5001 - Click Stop Auto Mining - Badge shows Auto Mining: OFF

---

## Common Issues and Solutions

### Issue: Balance shows 0 after generating wallet

Solution: The faucet reward is pending. It will show in balance immediately but you need to mine a block to fully confirm it. The balance should still show 100 even before mining.

### Issue: Transaction fails with insufficient balance

Solution: Make sure you have mined the faucet reward block first. Check your balance before making a transaction.

### Issue: Node 5001 does not have same transactions as node 5000

Solution: Make sure both nodes are registered with each other in the Configure page. Then submit a new transaction and it will broadcast automatically.

### Issue: Startup sync does not work

Solution: Make sure the peer node is running before restarting the offline node. The sync waits 3 seconds then contacts peers. If the peer is not running, sync will fail silently.

### Issue: DataTables warning in View Transactions

Solution: Press Ctrl+Shift+R to hard refresh the browser page. This clears the cached JavaScript.

---

## Summary of What Each Feature Does

    Wallet Generator    - Creates ECC secp256k1 key pair and gives 100 coin faucet reward
    Make Transaction    - Signs and sends transaction to blockchain node
    View Transactions   - Shows all confirmed transactions from any node
    Check Balance       - Shows wallet balance including pending received coins
    Mine button         - Manually mines pending transactions into a block
    Start Auto Mining   - Node automatically mines whenever transactions exist
    Configure           - Register peer nodes for network synchronization
    blockchain_5000.json - Node 5000 independent data storage
    blockchain_5001.json - Node 5001 independent data storage
    Startup sync        - Automatically downloads missing blocks on node restart

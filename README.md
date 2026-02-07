# StockTrack

## Project Description

### Stock tracker meant to allow users to track investment portfolio across brokerage accounts in one unified platform

### Current Status

#### Application is currently in CRUD stage where users enter date of transaction, shares, and price at time of purchase. 

### Currently working on

#### Main dashboard view to display basic profit/loss, data visualization, integrating Plaid API in future.

##### How to run locally: 
(Note: If you are on Windows device, use python instead of python3 for all commands below)
1. **Clone and Enter Project:**
Go to terminal, run git clone       , then type cd stocktrack
2. **Create Virtual Environment:**
Set up a virtual environment by running "python3 -m venv .venv"
3. **Activate Virtual Environment:**
Run ".venv\Scripts\activate" for Windows or "source .venv/bin/activate" on Mac/Linux to activate the virtual environment
4. **Install Dependencies:**
Install dependencies by running "pip install -r requirements.txt"
5. **Set up Environment File:**
Copy the ".env-example" file by running "cp .env-example .env" (copy on Windows)
6. **Set Database  URI:**
Go to this ".env" file and enter in any name for your URI
7. **Generate Secret Key:**
In terminal, enter python3 -c "import secrets; print(secrets.token_hex(32))"
8. **Save Secret Key:**
Copy this output into your SECRET_KEY variable in the .env file
9. **Launch App:**
Now, you can run this project by typing "python3 app.py", then clicking on the link provided in the terminal.

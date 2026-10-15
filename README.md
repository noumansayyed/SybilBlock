# SybilBlock — local prototype

## Stack
React + Vite, FastAPI, scikit-learn Random Forest, SQLite, Solidity + Hardhat.

## Screenshots

### Dashboard
![SybilBlock Dashboard](docs/images/dashboard.png)

### Analysis Results
![Analysis Results](docs/images/analysis-results.png)

### Blockchain Verification
![Blockchain Verification](docs/images/blockchain-verification.png)


## Run backend
Python 3.10+ recommended.
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
.venv/Scripts/activate
pip install -r requirements.txt
python train_model.py
uvicorn app.main:app --reload
```
API docs: http://127.0.0.1:8000/docs

## Run frontend (new terminal)
```bash
cd frontend
npm install
npm run dev
```
Open http://127.0.0.1:5173

## Optional real local blockchain
```bash
cd blockchain
npm install
npx hardhat compile
npx hardhat node
```
In another terminal:
```bash
cd blockchain
npx hardhat run scripts/deploy.js --network localhost
```
Copy deployed address into `backend/.env` and set:
```env.example to env and configure it 
BLOCKCHAIN_ENABLED=true
RPC_URL=http://127.0.0.1:8545
CONTRACT_ADDRESS=0xYOUR_DEPLOYED_CONTRACT
PRIVATE_KEY=PASTE_LOCAL_HARDHAT_ACCOUNT_KEY
```
Restart FastAPI. Use only a local Hardhat development key, never a real wallet key.

Without blockchain enabled, ML scoring and history still work and the app says `demo-only`. Synthetic data is for demonstration and is not proof of real-world accuracy.

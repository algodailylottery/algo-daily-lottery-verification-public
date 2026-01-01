# GitHub Setup Guide

Your opensource folder is ready to publish! Here's how to get it on GitHub.

## What's Included

### 📜 Core Scripts
- `verify_draw.py` - Main verification tool
- `get_seed_from_blockchain.py` - Blockchain seed retrieval
- `test_determinism.py` - Proof of deterministic behavior

### 📄 Smart Contract
- `lottery_contract.py` - Complete PyTeal source code (App ID: 3380359414)

### 📚 Documentation
- `README.md` - Main project overview
- `QUICKSTART.md` - 60-second setup guide
- `VERIFICATION_GUIDE.md` - Detailed user guide
- `VERIFICATION_DIAGRAM.md` - Visual diagrams and flows
- `BLOCKCHAIN_SEED_RETRIEVAL.md` - Blockchain data retrieval methods
- `EXAMPLE_OUTPUT.md` - Sample verification output

### 🛠️ Project Files
- `requirements.txt` - Python dependencies
- `LICENSE` - MIT License
- `.gitignore` - Git ignore rules

## Method 1: Using Git CLI (Recommended)

```bash
# Navigate to the opensource folder
cd opensource

# Initialize git
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Algorand lottery verification tools"

# Create GitHub repo first (https://github.com/new), then:
git remote add origin https://github.com/[YOUR-USERNAME]/lottery-verification.git
git branch -M main
git push -u origin main
```

## Method 2: GitHub Web Interface (Easiest)

1. Go to https://github.com/new
2. Repository name: `lottery-verification`
3. Description: `Provably fair lottery verification tools for Algorand Daily Lottery`
4. Make it **Public**
5. Don't initialize with README (we already have one)
6. Click "Create repository"
7. Click "uploading an existing file"
8. Drag all files from `opensource/` folder
9. Commit changes

## Method 3: GitHub Desktop

1. Open GitHub Desktop
2. File → Add Local Repository
3. Choose the `opensource` folder
4. Click "Publish repository"
5. Uncheck "Keep this code private"
6. Click "Publish Repository"

## After Publishing

### Update Links in README.md

Replace placeholders:
- `[YOUR-USERNAME]` with your GitHub username
- `[Your website]` with your lottery website
- `[Your discord]` with your Discord link
- `[Your email]` with your contact email

### Repository Settings

1. Go to repository Settings
2. Under "About" (top right on repo page):
   - Add description: "Provably fair lottery verification for Algorand"
   - Add topics: `algorand` `blockchain` `lottery` `verification` `provably-fair` `pyteal`
   - Add website URL

### Enable GitHub Pages (Optional)

Turn your documentation into a website:
1. Settings → Pages
2. Source: Deploy from branch
3. Branch: main / (root)
4. Save

Your docs will be at: `https://[your-username].github.io/lottery-verification/`

## Tweet Templates

### Simple Tweet
```
🔐 Algorand Daily Lottery is now open source!

✅ Smart contract (PyTeal)
✅ Verification scripts
✅ Complete documentation

Anyone can verify any draw. No trust needed.

https://github.com/[YOUR-USERNAME]/lottery-verification

#Algorand #ProvenFair
```

### Thread (High Engagement)
```
1/4 🔓 Just open-sourced our entire @Algorand lottery system

• PyTeal smart contract
• Winner verification tools
• Blockchain seed retrieval scripts

Why? Because "trust us" isn't good enough in Web3 👇

2/4 How it works:
🔹 Smart contract generates random seed on-chain
🔹 Seed is public & immutable
🔹 Winners selected using deterministic algorithm

Same seed = Same winners (always)

Anyone can verify. Everyone should verify.

3/4 We've already verified all past cycles:
✅ Cycle 1-7: All fair

Every single draw is mathematically provable.

Try it yourself:
```bash
python3 verify_draw.py 7
```

4/4 Full source code, docs, and examples:
https://github.com/[YOUR-USERNAME]/lottery-verification

This is what true transparency looks like. 🔐

#Algorand #BuildOnAlgorand #ProvenFair
```

## Need Help?

- GitHub Docs: https://docs.github.com/en/get-started
- Git Basics: https://git-scm.com/book/en/v2/Getting-Started-Installing-Git

---

**Ready to publish?** Just follow Method 1 or 2 above!

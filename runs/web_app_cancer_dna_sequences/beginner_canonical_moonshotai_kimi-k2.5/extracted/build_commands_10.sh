# 1. Create project folder and navigate to it
mkdir dna-app && cd dna-app

# 2. Create virtual environment (recommended)
python -m venv venv

# 3. Activate it
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the application
python app.py

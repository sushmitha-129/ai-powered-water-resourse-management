from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import pandas as pd
import numpy as np
from pulp import LpProblem, LpVariable, lpSum, LpMaximize

app = Flask(__name__)
DB_NAME = 'database.db'

# ------------------------
# Database Initialization
# ------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Communities table
    c.execute('''CREATE TABLE IF NOT EXISTS communities
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE, population INTEGER)''')
    # Daily usage table
    c.execute('''CREATE TABLE IF NOT EXISTS water_usage
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  community_id INTEGER,
                  date TEXT,
                  usage INTEGER,
                  FOREIGN KEY(community_id) REFERENCES communities(id))''')
    conn.commit()
    conn.close()

# ------------------------
# Helper Functions
# ------------------------
def get_data():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    df = pd.read_sql_query('''
        SELECT com.id as community_id, com.name as Community, com.population as Population,
               IFNULL(AVG(w.usage), 0) as Avg_Usage
        FROM communities com
        LEFT JOIN water_usage w ON com.id = w.community_id
        GROUP BY com.id
    ''', conn)
    conn.close()

    # Fill missing columns if no data
    if df.empty:
        df = pd.DataFrame(columns=['community_id','Community','Population','Avg_Usage'])

    # Add extra columns
    df['Current_Supply'] = df['Avg_Usage'] * df['Population'] * 1.1  # assume 10% extra
    df['Rainfall'] = np.random.randint(0,20,size=len(df))
    df['Temperature'] = np.random.randint(25,35,size=len(df))
    return df

def optimize_allocation(df):
    if len(df) == 0 or df['Avg_Usage'].sum() == 0:
        # No historical data yet
        df['Predicted_Demand'] = 0
        df['Shortage'] = False
        df['Optimized_Share'] = 0
        df['Final_Supply'] = df['Current_Supply']
        df['Payment'] = 0
        return df

    # Predict demand using simple formula (safe)
    df['Predicted_Demand'] = df['Population'] * df['Avg_Usage']
    df['Shortage'] = df['Current_Supply'] < df['Predicted_Demand']

    # Optimization using Linear Programming
    prob = LpProblem("Water_Sharing", LpMaximize)
    give = {c: LpVariable(f'give_{c}', lowBound=0) for c in df['Community']}
    prob += lpSum([give[c] for c in df['Community']])
    for i,row in df.iterrows():
        surplus = max(0, row['Current_Supply'] - row['Predicted_Demand'])
        prob += give[row['Community']] <= surplus
    prob.solve()
    df['Optimized_Share'] = [give[c].varValue if give[c].varValue else 0 for c in df['Community']]
    df['Final_Supply'] = df['Current_Supply'] - df['Optimized_Share']

    # Payment calculation (example: 0.5 per unit of water)
    df['Payment'] = df['Final_Supply'] * 0.5 / 1000  # scaled for demo
    return df

# ------------------------
# Routes
# ------------------------
@app.route('/', methods=['GET'])
def index():
    df = get_data()
    df = optimize_allocation(df)
    data = df.to_dict(orient='records')
    return render_template('index.html', data=data)

@app.route('/add_community', methods=['POST'])
def add_community():
    name = request.form['name']
    population = int(request.form['population'])
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO communities (name,population) VALUES (?,?)',(name,population))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/add_usage', methods=['POST'])
def add_usage():
    community_id = int(request.form['community_id'])
    date = request.form['date']
    usage = int(request.form['usage'])
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT INTO water_usage (community_id,date,usage) VALUES (?,?,?)',(community_id,date,usage))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/update_data', methods=['GET'])
def update_data():
    df = get_data()
    df = optimize_allocation(df)
    return jsonify(df.to_dict(orient='records'))

# ------------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)

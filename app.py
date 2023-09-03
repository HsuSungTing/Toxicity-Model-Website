from flask import Flask, render_template, request,redirect, url_for,session
import pyodbc
import os
import tensorflow as tf
from tensorflow.keras.models import load_model
from tensorflow.keras.layers import TextVectorization
import pandas as pd
import numpy as np


app = Flask(__name__)
# app.secret_key = 'your_secret_key_here'  # 替换为随机生成的密钥

# SQL Server连接配置
server = 'LAPTOP-Q69P3FAE\\MSSQLSERVER01'
database = 'user_DB'
username = 'sa'
password = '12345'
driver = '{ODBC Driver 17 for SQL Server}'  

hide_array=["OFF","OFF","OFF","OFF","OFF","OFF"]
sort_btn = 'ON'  # 默认按钮状态

def prepare_model(input_comment):
    # Load the trained model
    model_path = "./model2.h5"
    model = load_model(model_path)
    # Load the text vectorizer
    vectorizer = TextVectorization(max_tokens=200000, output_sequence_length=1800, output_mode='int')
    df = pd.read_csv(os.path.join('jigsaw-toxic-comment-classification-challenge','train.csv', 'train.csv'))

    X = df['comment_text'] #只抓文字留言搭配ID
    y = df.iloc[:, 2:]#只抓各種label搭配ID
    vectorizer.adapt(X.values)
    data = input_comment
    input_text = vectorizer([data])
    prediction = model.predict(np.array(input_text))
    return prediction

# -------------连接到数据库-------------------
def connect_to_database():
    connection = pyodbc.connect(f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}')
    return connection

# 执行查询并返回结果
def execute_query(query):
    connection = connect_to_database()
    cursor = connection.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    connection.close()
    return results

def find_Admin_data():
    global sort_btn
    global hide_array
    query = 'SELECT * FROM Admin_data'
    results = execute_query(query)
    if(int(results[0][1])==1):
        sort_btn="ON"
    else:
        sort_btn='OFF'
    for i in range(3,9):
        if(int(results[0][i])==1):
            hide_array[i-3]="ON"
        else:
            hide_array[i-3]="OFF"

find_Admin_data()
#建立local端的留言Table
def build_local_table():
    query = 'SELECT * FROM comment_data'
    results = execute_query(query)
    
    map=["toxic","severe toxic","obscene","threating","insulting","identity hating"]
    for y in range(len(results)):
        label_str="labels: "
        toxic_score=0
        for i in range(3,len(results[y])):
            if results[y][i]>=0.5:
                label_str=label_str+map[i-3]+"+"
                toxic_score=toxic_score+1
        results[y] = list(results[y])  # 將pyodbc.Row轉換為列表
        if label_str[len(label_str)-1]=="+":
            label_str=label_str[:-1]
        elif label_str=="labels: ":
            label_str="labels: Great!!!"
        results[y].append(label_str)
        results[y].append(toxic_score)
    return results

@app.route('/') #這份code目前的邏輯是在/的.html拿到username和user_ID之後，#進入/login，再去資料庫確認是否有這筆資料
def index():
    return render_template('login.html')

@app.route('/show_stats', methods=['GET', 'POST'])
def show_stats():
    query = 'SELECT * FROM user_data'
    results = execute_query(query)
    global hide_array
    global sort_btn
    
    if request.method == 'POST':
        sort_bool = None
        hide_bool_array = [0, 0, 0, 0, 0, 0]  # 初始化为0

        sort_btn_state = request.form.get('sort_btn_state')

        if sort_btn_state == 'ON':
            sort_btn = 'OFF'
            sort_bool = 0
            print("sort_btn_state == 'ON'")
        else:
            sort_btn = 'ON'
            sort_bool = 1
            print("sort_btn_state == 'OFF'")
        for i in range(6):
            button_name = f'button_{i + 1}'
            button_state = request.form.get(button_name)
            if button_state == 'ON':
                hide_array[i] = 'OFF'
                hide_bool_array[i] = 0
                print(f'button_{i + 1}',"ON")
            else:
                hide_array[i] = 'ON'
                hide_bool_array[i] = 1
                print(f'button_{i + 1}',"OFF")
        connection = connect_to_database()
        cursor = connection.cursor()
        # 在这里执行你的更新操作
        update_query = f"UPDATE Admin_data SET sort_bool='{sort_bool}', hide_toxic='{hide_bool_array[0]}', hide_severe='{hide_bool_array[1]}', hide_obscene='{hide_bool_array[2]}', hide_threat='{hide_bool_array[3]}', hide_insult='{hide_bool_array[4]}', hide_hate='{hide_bool_array[5]}' WHERE Admin_ID=1"
        cursor.execute(update_query)
        connection.commit()
        cursor.close()
        connection.close()

    return render_template('Admin_page.html', results=results, show_stats=True, show_preview=False, sort_btn=sort_btn, hide_array=hide_array)

# 添加留言区预览的路由
@app.route('/show_preview')
def show_preview():
    results=build_local_table()
    if(sort_btn=="ON"):
        results = sorted(results,key=lambda x: x[10])
    return render_template('Admin_page.html', show_preview=True,show_stats=False,results=results)
#------------------------------------------------------------------

@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        user_name = request.form['user_name'] #從前端拿取資料
        user_id= request.form['user_id']
        # 查询数据库是否存在匹配的用户
        query = f"SELECT * FROM user_data WHERE user_name='{user_name}' AND user_ID='{user_id}'"
        results = execute_query(query)

        if len(results) > 0:
            # return f"Login successful for user: {user_name}"
            return redirect(url_for('comment_section', user_name=user_name))
        else:
            return render_template('login.html', login_failed=True)

# 新增一个新的路由来显示用户信息和评论区
@app.route('/profile/<user_name>')
def comment_section(user_name):
    results=build_local_table()
    results = sorted(results,key=lambda x: x[10])
    return render_template('comment_section.html', user_name=user_name, results=results)

@app.route('/submit_comment', methods=['POST'])#建立user_data
def submit_comment():
    if request.method == 'POST':
        user_name = request.form['user_name']
        comment = request.form['comment']
        #------------------------------
        query = f"SELECT COUNT(*) FROM comment_data "
        results = execute_query(query)
        comment_ID = int(results[0][0])+1  
        #----------------------------------------------
        result_ary=prepare_model(comment)
        
        # 插入留言以及攻擊性機率到数据库
        connection = connect_to_database()
        cursor = connection.cursor()
        #----------------------------------------------
        insert_query = f"INSERT INTO comment_data (comment_ID,user_name, comment,toxic_prob,severe_toxic_prob,obscene_prob,threat_prob,insult_prob,identity_hate_prob) VALUES ('{comment_ID}','{user_name}', '{comment}', '{result_ary[0][0]}', '{result_ary[0][1]}', '{result_ary[0][2]}','{result_ary[0][3]}','{result_ary[0][4]}','{result_ary[0][5]}')"
        cursor.execute(insert_query)
        #------------------------------------------------
        toxic_bool_ary=[]
        for x in result_ary[0]:
            if(x>=0.5):
                toxic_bool_ary.append(1)
            else:
                toxic_bool_ary.append(0)
        update_query = f"UPDATE user_data SET toxic_ct = toxic_ct+'{ toxic_bool_ary[0]}', severe_toxic_ct = severe_toxic_ct+'{ toxic_bool_ary[1]}', obscene_ct = obscene_ct+'{ toxic_bool_ary[2]}',threat_ct = threat_ct+'{ toxic_bool_ary[3]}',insult_ct = insult_ct+'{ toxic_bool_ary[4]}',identity_hate_ct=identity_hate_ct+'{ toxic_bool_ary[5]}'  WHERE user_name = '{user_name}'"
        cursor.execute(update_query)
        connection.commit()
        cursor.close()
        connection.close()
        
        #重新導入至/comment_section 的路由
        return redirect(url_for('comment_section', user_name=user_name))

if __name__ == '__main__':
    app.run(debug=True)
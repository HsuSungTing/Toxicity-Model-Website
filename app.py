from flask import Flask, render_template, request,redirect, url_for,session
import pyodbc
import os
import tensorflow as tf
import torch
from transformers import BertTokenizer, BertForSequenceClassification
from torch.utils.data import DataLoader, TensorDataset
import pandas as pd
import numpy as np


app = Flask(__name__)

# SQL Server connection
server = 'LAPTOP-Q69P3FAE\\MSSQLSERVER01'
database = 'user_DB'
username = 'sa'
password = '12345'
driver = '{ODBC Driver 17 for SQL Server}'  
#initailize global value
hide_array=["OFF","OFF","OFF","OFF","OFF","OFF"]
sort_btn = 'OFF'  
block_user_btn="OFF"
hide_bool_array=[0,0,0,0,0,0]
sort_btn_bool=0
block_user_bool=0
block_threshold=0

model_name =".\saved_model"
device = torch.device('cpu')
Bert_Tokenizer = BertTokenizer.from_pretrained(model_name)
Bert_Model = BertForSequenceClassification.from_pretrained(model_name).to(device)

def prepare_model(input_text, model=Bert_Model, tokenizer=Bert_Tokenizer,device=device):
    user_input = [input_text]
    user_encodings = tokenizer(user_input, truncation=True, padding=True, return_tensors="pt")
    user_dataset = TensorDataset(user_encodings['input_ids'], user_encodings['attention_mask'])
    user_loader = DataLoader(user_dataset, batch_size=1, shuffle=False)
    model.eval()
    with torch.no_grad():
        for batch in user_loader:
            input_ids, attention_mask = [t.to(device) for t in batch]
            outputs = model(input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            predictions = torch.sigmoid(logits)

    predicted_labels = (predictions.cpu().numpy() > 0.5).astype(int)
    return predicted_labels[0].tolist()

# ------------連接到database-------------------
def connect_to_database():
    connection = pyodbc.connect(f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}')
    return connection

# 反覆被呼叫的query function
def execute_query(query):
    connection = connect_to_database()
    cursor = connection.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    connection.close()
    return results

def find_Admin_data(): #從資料庫抓取現在狀態
    global sort_btn,sort_btn_bool
    global hide_array, hide_bool_array
    global block_user_bool,block_user_btn
    global block_threshold
    query = 'SELECT * FROM Admin_data'
    results = execute_query(query)
    if(int(results[0][1])==1):
        sort_btn="ON"
        sort_btn_bool=1
    else:
        sort_btn='OFF'
        sort_btn_bool=0
    for i in range(3,9):
        if(int(results[0][i])==1):
            hide_array[i-3]="ON"
            hide_bool_array[i-3]=1
        else:
            hide_array[i-3]="OFF"
            hide_bool_array[i-3]=0
    if(results[0][9]==1):
        block_user_btn="ON"
        block_user_bool=1
    else:
        block_user_btn="OFF"
        block_user_bool=0
    block_threshold=results[0][2]
        
find_Admin_data()

#建立local端的留言Table
def build_local_table():
    query = 'SELECT * FROM comment_data'
    results = execute_query(query)
    
    map=["toxic","severe toxic","obscene","threating","insulting","identity hating"]
    for y in range(len(results)):
        label_str="labels: "
        toxic_score=0
        six_category_bool=[]
        for i in range(3,len(results[y])):
            if results[y][i]>=0.5:
                label_str=label_str+map[i-3]+"+"
                toxic_score=toxic_score+1
                six_category_bool.append(1)
            else:
                six_category_bool.append(0)
        results[y] = list(results[y])  # 將pyodbc.Row轉換為列表
        if label_str[len(label_str)-1]=="+":
            label_str=label_str[:-1]
        elif label_str=="labels: ":
            label_str="labels: Great!!!"
        results[y].append(label_str)
        results[y].append(toxic_score)
        results[y].append(six_category_bool)
    return results  #toxic_score在result[10]，#記錄所有屬性的list在result[11]

@app.route('/') #這份code目前的邏輯是在/的.html拿到username和user_ID之後，#進入/login，再去資料庫確認是否有這筆資料
def index():
    return render_template('login.html')

def update_Admin_data(sort_btn_bool,hide_bool_array,block_user_bool,block_threshold):
    connection = connect_to_database()
    cursor = connection.cursor()
    update_query = f"UPDATE Admin_data SET sort_bool='{sort_btn_bool}', hide_toxic='{hide_bool_array[0]}', hide_severe='{hide_bool_array[1]}', hide_obscene='{hide_bool_array[2]}', hide_threat='{hide_bool_array[3]}', hide_insult='{hide_bool_array[4]}', hide_hate='{hide_bool_array[5]}',block_user_bool='{block_user_bool}',toxic_def='{block_threshold}' WHERE Admin_ID=1"
    cursor.execute(update_query)
    connection.commit()
    cursor.close()
    connection.close()    
    
def toggle_button_state(index): #i從0開始
    i=index-1
    global hide_array,hide_bool_array
    global sort_btn_bool
    global block_user_bool
    global block_threshold
    button_name = f'button_{i + 1}'
    button_state = request.form.get(button_name)
    print("button_state",button_state)
    if button_state == 'ON':
        hide_array[i] = 'OFF'
        hide_bool_array[i] = 0
        # print(f'button_{i + 1}', 'OFF')
    else:
        hide_array[i] = 'ON'
        hide_bool_array[i] = 1
        # print(f'button_{i + 1}', 'ON')
    
    #寫入DB
    update_Admin_data(sort_btn_bool,hide_bool_array,block_user_bool,block_threshold)
        
#-----------------分別處理六個btn--------------
@app.route('/toggle_button/<int:index>', methods=['POST'])
def toggle_button(index):
    toggle_button_state(index)
    return redirect(url_for('show_stats'))

#處理是否要封鎖不良使用者的按鈕
@app.route('/block_user_router', methods=['POST'])
def block_user_router():
    global hide_bool_array
    global sort_btn_bool
    global block_user_bool,block_user_btn      #string
    global block_threshold
    button_state = request.form.get("block_user_state")
    if button_state == 'ON':
        block_user_btn = 'OFF'
        block_user_bool = 0
    else:
        block_user_btn  = 'ON'
        block_user_bool = 1
    #寫入DB
    update_Admin_data(sort_btn_bool,hide_bool_array,block_user_bool,block_threshold)
    return redirect(url_for('show_stats'))

@app.route('/get_toxic_def', methods=['POST'])
def get_toxic_def():
    global sort_btn_bool,hide_bool_array,block_user_bool,block_threshold
    block_threshold=int(request.form.get("block_user_int")) #從前端抓取
    print("toxic_def:",block_threshold)
    update_Admin_data(sort_btn_bool,hide_bool_array,block_user_bool,block_threshold)
    return redirect(url_for('show_stats'))

@app.route('/show_stats', methods=['GET', 'POST'])
def show_stats():
    query = 'SELECT * FROM user_data'
    results = execute_query(query)
    global hide_bool_array #把字串傳給前端
    global sort_btn,sort_btn_bool #唯一在這邊需要改動的bool
    global block_user_btn ,block_user_bool
    global block_threshold
    if request.method == 'POST':
        sort_btn_state = request.form.get('sort_btn_state')
        if sort_btn_state == 'ON':
            sort_btn = 'OFF'
            sort_btn_bool = 0
            print("sort_btn_state == 'ON'")
        else:
            sort_btn = 'ON'
            sort_btn_bool = 1
            print("sort_btn_state == 'OFF'")
        update_Admin_data(sort_btn_bool,hide_bool_array,block_user_bool,block_threshold)
    return render_template('Admin_page.html', results=results, show_stats=True, show_preview=False, sort_btn=sort_btn, hide_array=hide_array,block_user_btn=block_user_btn,default_block_user_int=block_threshold)

def remove_toxic_comment(hide_array,results):
    ans=[]
    remove_target=[]
    for i in range(0,6):
        if(hide_array[i]=="ON"):
            for j in range(0,len(results)):
                if results[j][11][i]==1:
                    print("results[j][11][i]",results[j][11][i])
                    remove_target.append(j)
    for i in range(0,len(results)):
        is_target_bool=0
        for j in range(0,len(remove_target)):
            if(i==remove_target[j]):
                is_target_bool=1
        if(is_target_bool==0):
            ans.append(results[i])
    return ans       

#在Admin_page.html顯示留言區的路由
@app.route('/show_preview')
def show_preview():
    global sort_btn
    global hide_array
    results=build_local_table()
    ans=remove_toxic_comment(hide_array,results)
    if(sort_btn=="ON"):
        ans = sorted(ans,key=lambda x: x[10])
    return render_template('Admin_page.html', show_preview=True,show_stats=False,results=ans)
#------------------------------------------------------------------

@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        global block_threshold
        global block_user_bool
        print("block_threshold,block_user_bool",block_threshold,block_user_bool)
        user_name = request.form['user_name'] #從前端拿取資料
        user_id= request.form['user_id']
        # 查询数据库是否存在匹配的用户
        query = f"SELECT * FROM user_data WHERE user_name='{user_name}' AND user_ID='{user_id}'"
        results = execute_query(query)
        print(results)
        if( (len(results) > 0 and block_threshold>results[0][8]) or (len(results) > 0 and block_user_bool==0)):
            # return f"Login successful for user: {user_name}"
            return redirect(url_for('comment_section', user_name=user_name))
        else:
            return render_template('login.html', login_failed=True)

#負責顯示留言區(在comment_section.html)
@app.route('/profile/<user_name>')
def comment_section(user_name):
    global hide_array
    results=build_local_table()
    ans=remove_toxic_comment(hide_array,results)
    global sort_btn_bool
    if(sort_btn_bool==1):
        results = sorted(results,key=lambda x: x[10])
    return render_template('comment_section.html', user_name=user_name, results=ans)

@app.route('/submit_comment', methods=['POST'])#建立user_data
def submit_comment():
    if request.method == 'POST':
        user_name = request.form['user_name']
        comment = request.form['comment']
        comment =comment.replace("'", "")
        #------------------------------
        query = f"SELECT COUNT(*) FROM comment_data "
        results = execute_query(query)
        comment_ID = int(results[0][0])+1  
        #----------------------------------------------
        result_ary=prepare_model(comment,Bert_Model,Bert_Tokenizer,device)
        # 插入留言以及攻擊性機率到数据库
        connection = connect_to_database()
        cursor = connection.cursor()
        #----------------------------------------------   
        insert_query = f"INSERT INTO comment_data (comment_ID,user_name, comment,toxic_prob,severe_toxic_prob,obscene_prob,threat_prob,insult_prob,identity_hate_prob) VALUES ('{comment_ID}','{user_name}', '{comment}', '{result_ary[0]}', '{result_ary[1]}', '{result_ary[2]}','{result_ary[3]}','{result_ary[4]}','{result_ary[5]}')"
        cursor.execute(insert_query)
        #------------------------------------------------
        violation_ct=0
        toxic_bool_ary=[]
        for x in result_ary:
            if(x>=0.5):
                toxic_bool_ary.append(1)
                violation_ct=violation_ct+1
            else:
                toxic_bool_ary.append(0)
        update_query = f"UPDATE user_data SET toxic_ct = toxic_ct+'{ toxic_bool_ary[0]}', severe_toxic_ct = severe_toxic_ct+'{ toxic_bool_ary[1]}', obscene_ct = obscene_ct+'{ toxic_bool_ary[2]}',threat_ct = threat_ct+'{ toxic_bool_ary[3]}',insult_ct = insult_ct+'{ toxic_bool_ary[4]}',identity_hate_ct=identity_hate_ct+'{ toxic_bool_ary[5]}',total=total+'{violation_ct}'  WHERE user_name = '{user_name}'"
        cursor.execute(update_query)
        connection.commit()
        cursor.close()
        connection.close()
        
        #重新導入至/comment_section 的路由
        return redirect(url_for('comment_section', user_name=user_name))

if __name__ == '__main__':
    app.run(debug=True)
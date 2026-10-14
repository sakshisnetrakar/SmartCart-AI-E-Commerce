"""Generate data, clean it, seed SQLite, train models, and save datasets/models."""
from pathlib import Path
import random
import joblib
import numpy as np
import pandas as pd
from passlib.context import CryptContext
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from database import connect, init_db

ROOT=Path(__file__).parent; DATA=ROOT/'data'; MODELS=ROOT/'models'; DATA.mkdir(exist_ok=True); MODELS.mkdir(exist_ok=True)
pwd=CryptContext(schemes=['bcrypt'], deprecated='auto')

def build():
    random.seed(42); np.random.seed(42); init_db()
    if (MODELS/'purchase_model.pkl').exists(): return
    cities=['Bengaluru','Mumbai','Delhi','Hyderabad','Chennai']; cats=['Electronics','Fashion','Home','Books','Sports']; payments=['UPI','Card','Cash on Delivery','Net Banking']
    customers=pd.DataFrame([{'customer_id':i,'name':f'Customer {i}','email':f'customer{i}@smartcart.local','password_hash':pwd.hash('password123'),'role':'admin' if i==1 else 'customer','age':random.randint(18,65),'gender':random.choice(['Female','Male','Other']),'city':random.choice(cities),'registration_date':'2026-01-01','total_purchases':random.randint(1,35),'total_spending':round(random.uniform(1500,90000),2),'website_visits':random.randint(5,200)} for i in range(1,101)])
    customers['average_order_value']=(customers.total_spending/customers.total_purchases).round(2)
    products=pd.DataFrame([{'product_id':i,'product_name':f'{random.choice(cats)} Product {i}','category':random.choice(cats),'price':round(random.uniform(199,12000),2),'rating':round(random.uniform(3,5),1),'stock':random.randint(2,100),'discount':random.choice([0,5,10,15,20])} for i in range(1,51)])
    orders=pd.DataFrame([{'order_id':i,'customer_id':random.randint(1,100),'product_id':random.randint(1,50),'quantity':random.randint(1,3),'order_date':f'2026-{random.randint(1,9):02d}-{random.randint(1,28):02d}','price':round(random.uniform(199,12000),2),'payment_method':random.choice(payments),'order_status':'Delivered'} for i in range(1,501)])
    activity=pd.DataFrame([{'customer_id':random.randint(1,100),'product_id':random.randint(1,50),'product_views':random.randint(0,25),'cart_additions':random.randint(0,5),'wishlist_additions':random.randint(0,4),'previous_purchases':random.randint(0,10),'time_spent':round(random.uniform(10,900),1)} for _ in range(1000)]).drop_duplicates(['customer_id','product_id'])
    merged=activity.merge(customers[['customer_id','age','total_purchases','total_spending','average_order_value','website_visits']],on='customer_id').merge(products[['product_id','price','rating']],on='product_id')
    score=.12*merged.product_views+.8*merged.cart_additions+.4*merged.wishlist_additions+.15*merged.previous_purchases+.001*merged.time_spent+np.random.normal(0,1,len(merged))
    merged['purchased']=(score>score.quantile(.55)).astype(int); activity['purchased']=merged['purchased'].values
    for name,frame in [('customers',customers),('products',products),('orders',orders),('customer_activity',activity)]: frame.to_csv(DATA/f'{name}.csv',index=False)
    # Cleaning: remove duplicates, fill ratings, validate age/prices
    products=products.drop_duplicates('product_id'); products['rating']=products.rating.fillna(products.rating.median()); customers=customers[(customers.age.between(18,100))]; products=products[products.price>=0]
    with connect() as c:
        c.executemany('INSERT OR REPLACE INTO customers VALUES (:customer_id,:name,:email,:password_hash,:role,:age,:gender,:city,:registration_date,:total_purchases,:total_spending,:average_order_value,:website_visits,:segment)', customers.assign(segment='Occasional Customer').to_dict('records'))
        c.executemany('INSERT OR REPLACE INTO products VALUES (:product_id,:product_name,:category,:price,:rating,:stock,:discount)',products.to_dict('records'))
        for o in orders.to_dict('records'):
            c.execute('INSERT INTO orders(order_id,customer_id,order_date,total,payment_method,order_status) VALUES(?,?,?,?,?,?)',(o['order_id'],o['customer_id'],o['order_date'],o['price']*o['quantity'],o['payment_method'],o['order_status']))
            c.execute('INSERT INTO order_items(order_id,product_id,quantity,price) VALUES(?,?,?,?)',(o['order_id'],o['product_id'],o['quantity'],o['price']))
        c.executemany('INSERT OR REPLACE INTO customer_activity VALUES (:customer_id,:product_id,:product_views,:cart_additions,:wishlist_additions,:previous_purchases,:time_spent,:purchased)',activity.to_dict('records'))
    features=['age','total_purchases','total_spending','average_order_value','website_visits','price','rating','product_views','cart_additions','wishlist_additions','previous_purchases','time_spent']
    X=merged[features]; y=merged.purchased; Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.25,random_state=42,stratify=y); scaler=StandardScaler(); Xtr_s=scaler.fit_transform(Xtr); Xte_s=scaler.transform(Xte)
    models={'Logistic Regression':LogisticRegression(max_iter=1000),'Decision Tree':DecisionTreeClassifier(random_state=42),'Random Forest':RandomForestClassifier(n_estimators=150,random_state=42)}; metrics={}; best=None; best_auc=-1
    for name,model in models.items():
        model.fit(Xtr_s,ytr); prob=model.predict_proba(Xte_s)[:,1]; pred=(prob>=.5).astype(int); metrics[name]={'accuracy':round(accuracy_score(yte,pred),3),'precision':round(precision_score(yte,pred),3),'recall':round(recall_score(yte,pred),3),'f1':round(f1_score(yte,pred),3),'roc_auc':round(roc_auc_score(yte,prob),3)}
        if metrics[name]['roc_auc']>best_auc: best_auc=metrics[name]['roc_auc']; best=model
    joblib.dump(best,MODELS/'purchase_model.pkl');joblib.dump(scaler,MODELS/'purchase_scaler.pkl');joblib.dump(features,MODELS/'features.pkl');joblib.dump(metrics,MODELS/'model_metrics.pkl')
    segment_features=customers[['total_purchases','total_spending','average_order_value','website_visits']]; seg_scaler=StandardScaler(); km=KMeans(n_clusters=4,random_state=42,n_init=10); labels=km.fit_predict(seg_scaler.fit_transform(segment_features)); names=['Premium Customer','Regular Customer','Occasional Customer','At-Risk Customer']; mapping={label:names[label] for label in range(4)}
    with connect() as c:
        for cid,label in zip(customers.customer_id,labels): c.execute('UPDATE customers SET segment=? WHERE customer_id=?',(mapping[label],int(cid)))
    joblib.dump(km,MODELS/'segment_model.pkl');joblib.dump(seg_scaler,MODELS/'segment_scaler.pkl')

if __name__=='__main__': build()

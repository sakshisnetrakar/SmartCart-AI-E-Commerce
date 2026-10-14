from pathlib import Path
from datetime import datetime,timedelta,timezone
import jwt,joblib
from fastapi import FastAPI,HTTPException,Depends
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel,Field,EmailStr
from database import connect
from seed_and_train import build

build(); ROOT=Path(__file__).parent; app=FastAPI(title='SmartCart AI E-Commerce'); auth=HTTPBearer(); pwd=CryptContext(schemes=['bcrypt'],deprecated='auto'); SECRET='local-development-only-secret'
class CustomerIn(BaseModel): name:str;email:EmailStr;password:str=Field(min_length=6);age:int=Field(ge=18,le=100);gender:str='Other';city:str
class ProductIn(BaseModel): product_name:str;category:str;price:float=Field(gt=0);rating:float=Field(ge=0,le=5);stock:int=Field(ge=0);discount:float=Field(ge=0,le=100)
class CartIn(BaseModel): customer_id:int;product_id:int;quantity:int=Field(gt=0)
class LoginIn(BaseModel): email:EmailStr;password:str
def rows(q,args=()):
 with connect() as c:return [dict(x) for x in c.execute(q,args).fetchall()]
def one(q,args=()):
 r=rows(q,args);return r[0] if r else None
def user(token:HTTPAuthorizationCredentials=Depends(auth)):
 try:return jwt.decode(token.credentials,SECRET,algorithms=['HS256'])
 except Exception:raise HTTPException(401,'Invalid login token')
def admin(u=Depends(user)):
 if u['role']!='admin':raise HTTPException(403,'Admin access required')
 return u
@app.get('/',include_in_schema=False)
def home():return FileResponse(ROOT/'static'/'index.html')
@app.post('/register')
def register(x:CustomerIn):
 with connect() as c:
  try:c.execute('INSERT INTO customers(name,email,password_hash,role,age,gender,city,registration_date,total_purchases,total_spending,average_order_value,website_visits) VALUES(?,?,?,?,?,?,?,?,0,0,0,0)',(x.name,x.email,pwd.hash(x.password),'customer',x.age,x.gender,x.city,datetime.now().date().isoformat()));return {'message':'Registered'}
  except Exception:raise HTTPException(409,'Duplicate email')
@app.post('/login')
def login(x:LoginIn):
 u=one('SELECT * FROM customers WHERE email=?',(x.email,))
 if not u or not pwd.verify(x.password,u['password_hash']):raise HTTPException(401,'Invalid login')
 return {'access_token':jwt.encode({'sub':u['customer_id'],'role':u['role'],'exp':datetime.now(timezone.utc)+timedelta(hours=8)},SECRET,algorithm='HS256'),'token_type':'bearer'}
@app.post('/customers')
def create_customer(x:CustomerIn):return register(x)
@app.get('/customers')
def customers():return rows('SELECT customer_id,name,email,age,gender,city,total_spending,segment FROM customers')
@app.get('/customers/{cid}')
def customer(cid:int):
 x=one('SELECT customer_id,name,email,age,gender,city,total_spending,segment FROM customers WHERE customer_id=?',(cid,));
 if not x:raise HTTPException(404,'Customer not found')
 return x
@app.put('/customers/{cid}')
def update_customer(cid:int,x:CustomerIn):
 with connect() as c:c.execute('UPDATE customers SET name=?,email=?,age=?,gender=?,city=? WHERE customer_id=?',(x.name,x.email,x.age,x.gender,x.city,cid))
 return customer(cid)
@app.delete('/customers/{cid}')
def delete_customer(cid:int):
 with connect() as c:c.execute('DELETE FROM customers WHERE customer_id=?',(cid,))
 return {'message':'Deleted'}
@app.post('/products')
def create_product(x:ProductIn):
 with connect() as c:
  cur=c.execute('INSERT INTO products(product_name,category,price,rating,stock,discount) VALUES(?,?,?,?,?,?)',tuple(x.model_dump().values()));return {'product_id':cur.lastrowid}
@app.get('/products')
def products():return rows('SELECT * FROM products')
@app.get('/products/{pid}')
def product(pid:int):
 x=one('SELECT * FROM products WHERE product_id=?',(pid,));
 if not x:raise HTTPException(404,'Product not found')
 return x
@app.put('/products/{pid}')
def update_product(pid:int,x:ProductIn):
 with connect() as c:c.execute('UPDATE products SET product_name=?,category=?,price=?,rating=?,stock=?,discount=? WHERE product_id=?',(*x.model_dump().values(),pid))
 return product(pid)
@app.delete('/products/{pid}')
def delete_product(pid:int):
 with connect() as c:c.execute('DELETE FROM products WHERE product_id=?',(pid,))
 return {'message':'Deleted'}
@app.post('/cart')
def add_cart(x:CartIn):
 if not customer_exists(x.customer_id) or not one('SELECT 1 FROM products WHERE product_id=?',(x.product_id,)):raise HTTPException(404,'Customer or product not found')
 with connect() as c:c.execute('INSERT INTO cart(customer_id,product_id,quantity) VALUES(?,?,?) ON CONFLICT(customer_id,product_id) DO UPDATE SET quantity=quantity+excluded.quantity',(x.customer_id,x.product_id,x.quantity))
 return {'message':'Added to cart'}
def customer_exists(cid):return bool(one('SELECT 1 AS ok FROM customers WHERE customer_id=?',(cid,)))
@app.get('/cart/{cid}')
def cart(cid:int):return rows('SELECT cart.cart_id,products.product_name,products.price,cart.quantity FROM cart JOIN products USING(product_id) WHERE customer_id=?',(cid,))
@app.put('/cart/{cart_id}')
def update_cart(cart_id:int,x:CartIn):
 with connect() as c:c.execute('UPDATE cart SET quantity=? WHERE cart_id=?',(x.quantity,cart_id))
 return {'message':'Updated'}
@app.delete('/cart/{cart_id}')
def delete_cart(cart_id:int):
 with connect() as c:c.execute('DELETE FROM cart WHERE cart_id=?',(cart_id,))
 return {'message':'Deleted'}

@app.post('/orders')
def place_order(customer_id:int,payment_method:str='UPI'):
 items=rows('SELECT cart.product_id,cart.quantity,products.price,products.stock FROM cart JOIN products USING(product_id) WHERE customer_id=?',(customer_id,))
 if not items:raise HTTPException(400,'Empty cart')
 if any(x['quantity']>x['stock'] for x in items):raise HTTPException(400,'Insufficient stock')
 total=sum(x['quantity']*x['price'] for x in items)
 with connect() as c:
  cur=c.execute('INSERT INTO orders(customer_id,order_date,total,payment_method,order_status) VALUES(?,?,?,?,?)',(customer_id,datetime.now().date().isoformat(),total,payment_method,'Placed'));oid=cur.lastrowid
  for x in items:
   c.execute('INSERT INTO order_items(order_id,product_id,quantity,price) VALUES(?,?,?,?)',(oid,x['product_id'],x['quantity'],x['price']));c.execute('UPDATE products SET stock=stock-? WHERE product_id=?',(x['quantity'],x['product_id']))
  c.execute('DELETE FROM cart WHERE customer_id=?',(customer_id,))
 return {'order_id':oid,'total':total,'status':'Placed'}
@app.get('/orders')
def orders():return rows('SELECT * FROM orders')
@app.get('/orders/{oid}')
def order(oid:int):
 x=one('SELECT * FROM orders WHERE order_id=?',(oid,));
 if not x:raise HTTPException(404,'Order not found')
 return x
@app.get('/customers/{cid}/orders')
def customer_orders(cid:int):return rows('SELECT * FROM orders WHERE customer_id=?',(cid,))
def prediction(cid,pid):
 c=one('SELECT * FROM customers WHERE customer_id=?',(cid,));p=one('SELECT * FROM products WHERE product_id=?',(pid,));a=one('SELECT * FROM customer_activity WHERE customer_id=? AND product_id=?',(cid,pid))
 if not c:raise HTTPException(404,'Customer not found')
 if not p:raise HTTPException(404,'Product not found')
 a=a or {'product_views':0,'cart_additions':0,'wishlist_additions':0,'previous_purchases':0,'time_spent':0}
 features=joblib.load(ROOT/'models'/'features.pkl');model=joblib.load(ROOT/'models'/'purchase_model.pkl');scaler=joblib.load(ROOT/'models'/'purchase_scaler.pkl')
 row=[[c['age'],c['total_purchases'],c['total_spending'],c['average_order_value'],c['website_visits'],p['price'],p['rating'],a['product_views'],a['cart_additions'],a['wishlist_additions'],a['previous_purchases'],a['time_spent']]];prob=float(model.predict_proba(scaler.transform(row))[0][1]);return {'customer_id':cid,'product_id':pid,'purchase_probability':round(prob,2),'prediction':'Likely to Purchase' if prob>=.5 else 'Unlikely to Purchase'}
@app.post('/predict-purchase')
def predict_purchase(customer_id:int,product_id:int):return prediction(customer_id,product_id)
@app.get('/recommendations/{cid}')
def recommendations(cid:int):
 if not customer_exists(cid):raise HTTPException(404,'Customer not found')
 purchased=[x['product_id'] for x in rows('SELECT product_id FROM order_items JOIN orders USING(order_id) WHERE customer_id=?',(cid,))];q='SELECT * FROM products'+(' WHERE product_id NOT IN ('+','.join('?'*len(purchased))+')' if purchased else '')+' ORDER BY rating DESC,discount DESC LIMIT 5';items=rows(q,tuple(purchased));return {'customer_id':cid,'recommendations':[{'product_id':x['product_id'],'product_name':x['product_name'],'score':round((x['rating']/5)*(1+x['discount']/100),2)} for x in items]}
@app.get('/customer-segment/{cid}')
def segment(cid:int):
 x=customer(cid);return {'customer_id':cid,'segment':x['segment']}
@app.get('/customer-dashboard/{cid}')
def dashboard(cid:int):
 c=customer(cid);os=customer_orders(cid);rec=recommendations(cid)['recommendations'];return {'customer':c,'total_orders':len(os),'total_spending':sum(x['total'] for x in os),'average_order_value':round(sum(x['total'] for x in os)/len(os),2) if os else 0,'previous_purchases':c['total_purchases'],'customer_segment':c['segment'],'recommended_products':rec,'sample_purchase_prediction':prediction(cid,rec[0]['product_id']) if rec else None}
@app.get('/admin/sales-summary')
def sales_summary(_:dict=Depends(admin)):return one('SELECT COUNT(*) total_orders,ROUND(SUM(total),2) total_revenue,ROUND(AVG(total),2) average_order_value FROM orders')
@app.get('/admin/top-products')
def top_products(_:dict=Depends(admin)):return rows('SELECT products.product_name,SUM(order_items.quantity) units,SUM(order_items.quantity*order_items.price) revenue FROM order_items JOIN products USING(product_id) GROUP BY product_id ORDER BY revenue DESC LIMIT 10')
@app.get('/admin/top-customers')
def top_customers(_:dict=Depends(admin)):return rows('SELECT customers.name,SUM(orders.total) spending FROM orders JOIN customers USING(customer_id) GROUP BY customer_id ORDER BY spending DESC LIMIT 10')
@app.get('/admin/category-sales')
def category_sales(_:dict=Depends(admin)):return rows('SELECT products.category,SUM(order_items.quantity*order_items.price) revenue FROM order_items JOIN products USING(product_id) GROUP BY products.category ORDER BY revenue DESC')
@app.get('/admin/customer-segments')
def customer_segments(_:dict=Depends(admin)):return rows('SELECT segment,COUNT(*) customers FROM customers GROUP BY segment')
@app.get('/admin/low-stock-products')
def low_stock(_:dict=Depends(admin)):return rows('SELECT * FROM products WHERE stock<10')

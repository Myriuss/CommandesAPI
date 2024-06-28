from fastapi import FastAPI, HTTPException, Depends, Security, status
from sqlalchemy import Column, Integer, ForeignKey, String, Float, create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base, relationship
from pydantic import BaseModel
from typing import List
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer
from confluent_kafka import Producer

# Initialize FastAPI
app = FastAPI()

# Configure SQLALCHEMY_DATABASE_URL
SQLALCHEMY_DATABASE_URL = "sqlite:///./order.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Define database models
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, index=True)
    total_amount = Column(Float, index=True)
    status = Column(String, default="pending")

    order_details = relationship("OrderDetail", back_populates="order")

class OrderDetail(Base):
    __tablename__ = "order_details"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)

    order = relationship("Order", back_populates="order_details")
    product = relationship("Product", back_populates="order_details")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, index=True)
    price = Column(Float, index=True)

    order_details = relationship("OrderDetail", back_populates="product")

# Create the database tables
Base.metadata.create_all(bind=engine)

# Pydantic models
class OrderBase(BaseModel):
    customer_name: str
    total_amount: float

class OrderCreate(OrderBase):
    pass

class OrderResponse(OrderBase):
    id: int
    status: str

    class Config:
        orm_mode = True

class OrderDetailBase(BaseModel):
    product_id: int
    quantity: int

class OrderDetailCreate(OrderDetailBase):
    pass

class OrderDetailResponse(OrderDetailBase):
    id: int
    order_id: int

    class Config:
        orm_mode = True

class ProductBase(BaseModel):
    name: str
    description: str
    price: float

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: int

    class Config:
        orm_mode = True

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Kafka configuration
KAFKA_BROKER_URL = 'localhost:9092'  # Replace with your Kafka broker URL
KAFKA_TOPIC = 'orders'

producer = Producer({'bootstrap.servers': KAFKA_BROKER_URL})

def delivery_report(err, msg):
    if err is not None:
        print('Message delivery failed: {}'.format(err))
    else:
        print('Message delivered to {} [{}]'.format(msg.topic(), msg.partition()))

def send_kafka_message(message):
    producer.produce(KAFKA_TOPIC, value=message, callback=delivery_report)
    producer.poll(1)

# Token Settings
SECRET_KEY = "your-secret-key"  # Replace with a secure random key in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token functions
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

# CRUD operations for orders
@app.post("/token")
def login_for_access_token(username: str, password: str):
    # Replace with actual authentication logic, verify username/password
    # For simplicity, let's assume a hardcoded user for demonstration
    if username == "user" and password == "password":
        access_token = create_access_token(data={"sub": username})
        return {"access_token": access_token, "token_type": "bearer"}
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

@app.post("/orders/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(order: OrderCreate, db: Session = Depends(get_db), token_data: dict = Depends(verify_token)):
    db_order = Order(**order.dict())
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    send_kafka_message(f"Order created: {db_order.id}")
    return db_order

@app.get("/orders/", response_model=List[OrderResponse])
def read_orders(skip: int = 0, limit: int = 10, db: Session = Depends(get_db), token_data: dict = Depends(verify_token)):
    orders = db.query(Order).offset(skip).limit(limit).all()
    return orders

@app.get("/orders/{order_id}", response_model=OrderResponse)
def read_order(order_id: int, db: Session = Depends(get_db), token_data: dict = Depends(verify_token)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order

@app.put("/orders/{order_id}", response_model=OrderResponse)
def update_order(order_id: int, order: OrderCreate, db: Session = Depends(get_db), token_data: dict = Depends(verify_token)):
    db_order = db.query(Order).filter(Order.id == order_id).first()
    if db_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    for attr, value in order.dict().items():
        setattr(db_order, attr, value)
    db.commit()
    db.refresh(db_order)
    send_kafka_message(f"Order updated: {db_order.id}")
    return db_order

@app.delete("/orders/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db), token_data: dict = Depends(verify_token)):
    db_order = db.query(Order).filter(Order.id == order_id).first()
    if db_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    db.delete(db_order)
    db.commit()
    send_kafka_message(f"Order deleted: {order_id}")
    return {"message": "Order deleted"}

# CRUD operations for order details
@app.post("/orders/{order_id}/details/", response_model=OrderDetailResponse, status_code=status.HTTP_201_CREATED)
def create_order_detail(order_id: int, order_detail: OrderDetailCreate, db: Session = Depends(get_db), token_data: dict = Depends(verify_token)):
    db_order_detail = OrderDetail(**order_detail.dict(), order_id=order_id)
    db.add(db_order_detail)
    db.commit()
    db.refresh(db_order_detail)
    send_kafka_message(f"Order detail created: {db_order_detail.id}")
    return db_order_detail

@app.get("/orders/{order_id}/details/", response_model=List[OrderDetailResponse])
def read_order_details(order_id: int, db: Session = Depends(get_db), token_data: dict = Depends(verify_token)):
    order_details = db.query(OrderDetail).filter(OrderDetail.order_id == order_id).all()
    return order_details

#if __name__ == "__main__":
#    import uvicorn
#    uvicorn.run(app, host="127.0.0.1", port=8000)
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, create_engine, desc, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class Settings(BaseSettings):
    database_url: str = "sqlite:///./ecommerce.db"
    db_echo: bool = False
    jwt_secret_key: str = "change-this-secret-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
if settings.database_url.startswith("postgres://"):
    settings.database_url = settings.database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif settings.database_url.startswith("postgresql://"):
    settings.database_url = settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=settings.db_echo, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    password_hash: Mapped[str] = mapped_column(Text)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    category_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True, index=True)
    stock_qty: Mapped[int] = mapped_column(default=0)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProductImage(Base):
    __tablename__ = "product_images"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True)
    image_url: Mapped[str] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(default=False)


class Address(Base):
    __tablename__ = "addresses"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(50), default="Home")
    address_line: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))
    postal_code: Mapped[str] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(100), default="India")
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Cart(Base):
    __tablename__ = "cart"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"))
    quantity: Mapped[int] = mapped_column(default=1)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    address_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("addresses.id"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column()
    price_at_purchase: Mapped[Decimal] = mapped_column(Numeric(10, 2))


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=15)
    password: str = Field(min_length=6)
    address: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=15)
    password: Optional[str] = Field(default=None, min_length=6)
    address: Optional[str] = None

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; name: str; email: EmailStr; phone: Optional[str]; address: Optional[str]; created_at: datetime

class CategoryIn(BaseModel): name: str = Field(min_length=1, max_length=100)
class CategoryOut(CategoryIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID

class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    category_id: Optional[UUID] = None
    stock_qty: int = Field(default=0, ge=0)
    image_url: Optional[str] = None
class ProductOut(ProductIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; created_at: datetime

class ProductImageIn(BaseModel):
    image_url: str = Field(min_length=1)
    is_primary: bool = False
class ProductImageOut(ProductImageIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; product_id: UUID

class AddressIn(BaseModel):
    label: str = Field(default="Home", min_length=1, max_length=50)
    address_line: str = Field(min_length=1)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=1, max_length=20)
    country: str = Field(default="India", min_length=1, max_length=100)
    is_default: bool = False
class AddressOut(AddressIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; user_id: UUID; created_at: datetime

class CartIn(BaseModel):
    user_id: UUID; product_id: UUID; quantity: int = Field(default=1, gt=0)
class CartUpdate(BaseModel): quantity: int = Field(gt=0)
class CartOut(CartIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; added_at: datetime

class OrderItemIn(BaseModel): product_id: UUID; quantity: int = Field(gt=0)
class OrderCreate(BaseModel):
    user_id: UUID; address_id: UUID; items: list[OrderItemIn] = Field(min_length=1)
class OrderStatusUpdate(BaseModel): status: str = Field(pattern="^(pending|shipped|delivered|cancelled)$")
class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; order_id: UUID; product_id: UUID; quantity: int; price_at_purchase: Decimal
class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; user_id: UUID; address_id: UUID; total_amount: Decimal; status: str; created_at: datetime


def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def get_or_404(db: Session, model, obj_id: UUID):
    obj = db.get(model, obj_id)
    if not obj: raise HTTPException(404, f"{model.__tablename__} record not found")
    return obj

def ensure_unique_email(db: Session, email: str, current: Optional[UUID] = None):
    q = db.scalar(select(User).where(User.email == email))
    if q and q.id != current: raise HTTPException(409, "Email already registered")

def create_access_token(user: User) -> tuple[str, int]:
    expires_in = settings.access_token_expire_minutes * 60
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    payload = {"sub": str(user.id), "email": user.email, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm), expires_in

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=401,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if not user_id: raise credentials_error
        user = db.get(User, UUID(user_id))
    except (JWTError, ValueError):
        raise credentials_error
    if not user: raise credentials_error
    return user

def require_user_id(requested_id: UUID, current_user: User):
    if requested_id != current_user.id:
        raise HTTPException(403, "You can only access your own user data")

def require_order_owner(order: Order, current_user: User):
    if order.user_id != current_user.id:
        raise HTTPException(403, "You can only access your own orders")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield

app = FastAPI(title="E-commerce CRUD API", version="1.0.0", lifespan=lifespan)

@app.get("/health")
def health(): return {"status": "ok"}

@app.post("/auth/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not pwd_context.verify(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password", headers={"WWW-Authenticate": "Bearer"})
    token, expires_in = create_access_token(user)
    return TokenOut(access_token=token, expires_in=expires_in)

@app.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    ensure_unique_email(db, payload.email)
    user = User(name=payload.name, email=payload.email, phone=payload.phone, address=payload.address, password_hash=pwd_context.hash(payload.password))
    db.add(user); db.commit(); db.refresh(user); return user

@app.get("/users", response_model=list[UserOut])
def list_users(current_user: User = Depends(get_current_user)):
    return [current_user]

@app.get("/users/{id}", response_model=UserOut)
def get_user(id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_user_id(id, current_user); return get_or_404(db, User, id)

@app.patch("/users/{id}", response_model=UserOut)
def update_user(id: UUID, payload: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_user_id(id, current_user)
    user = get_or_404(db, User, id); data = payload.model_dump(exclude_unset=True)
    if "email" in data: ensure_unique_email(db, data["email"], id)
    if "password" in data: user.password_hash = pwd_context.hash(data.pop("password"))
    for key, value in data.items(): setattr(user, key, value)
    db.commit(); db.refresh(user); return user

@app.delete("/users/{id}", status_code=204)
def delete_user(id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_user_id(id, current_user)
    db.delete(get_or_404(db, User, id)); db.commit()

@app.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(payload: CategoryIn, db: Session = Depends(get_db)):
    if db.scalar(select(Category).where(Category.name == payload.name)): raise HTTPException(409, "Category already exists")
    obj = Category(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj

@app.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)): return db.scalars(select(Category)).all()

@app.get("/categories/{id}", response_model=CategoryOut)
def get_category(id: UUID, db: Session = Depends(get_db)): return get_or_404(db, Category, id)

@app.patch("/categories/{id}", response_model=CategoryOut)
def update_category(id: UUID, payload: CategoryIn, db: Session = Depends(get_db)):
    obj = get_or_404(db, Category, id); obj.name = payload.name; db.commit(); db.refresh(obj); return obj

@app.delete("/categories/{id}", status_code=204)
def delete_category(id: UUID, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Category, id)); db.commit()

@app.post("/products", response_model=ProductOut, status_code=201)
def create_product(payload: ProductIn, db: Session = Depends(get_db)):
    if payload.category_id: get_or_404(db, Category, payload.category_id)
    obj = Product(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj

@app.get("/products", response_model=list[ProductOut])
def list_products(name: Optional[str] = None, min_price: Optional[Decimal] = Query(default=None, ge=0), max_price: Optional[Decimal] = Query(default=None, ge=0), sort: Optional[str] = Query(default=None, pattern="^(price_asc|price_desc)$"), category_id: Optional[UUID] = None, skip: int = 0, limit: int = Query(50, le=100), db: Session = Depends(get_db)):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(400, "min_price cannot be greater than max_price")
    q = select(Product)
    if name: q = q.where(Product.name.ilike(f"%{name.strip()}%"))
    if min_price is not None: q = q.where(Product.price >= min_price)
    if max_price is not None: q = q.where(Product.price <= max_price)
    if category_id: q = q.where(Product.category_id == category_id)
    if sort == "price_asc": q = q.order_by(Product.price.asc())
    elif sort == "price_desc": q = q.order_by(desc(Product.price))
    return db.scalars(q.offset(skip).limit(limit)).all()

@app.get("/products/{id}", response_model=ProductOut)
def get_product(id: UUID, db: Session = Depends(get_db)): return get_or_404(db, Product, id)

@app.patch("/products/{id}", response_model=ProductOut)
def update_product(id: UUID, payload: ProductIn, db: Session = Depends(get_db)):
    obj = get_or_404(db, Product, id)
    if payload.category_id: get_or_404(db, Category, payload.category_id)
    for key, value in payload.model_dump().items(): setattr(obj, key, value)
    db.commit(); db.refresh(obj); return obj

@app.delete("/products/{id}", status_code=204)
def delete_product(id: UUID, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Product, id)); db.commit()

@app.post("/products/{product_id}/images", response_model=ProductImageOut, status_code=201)
def add_product_image(product_id: UUID, payload: ProductImageIn, db: Session = Depends(get_db)):
    get_or_404(db, Product, product_id)
    has_images = db.scalar(select(ProductImage.id).where(ProductImage.product_id == product_id)) is not None
    if payload.is_primary or not has_images:
        db.query(ProductImage).filter(ProductImage.product_id == product_id).update({ProductImage.is_primary: False})
        payload.is_primary = True
    image = ProductImage(product_id=product_id, **payload.model_dump())
    db.add(image); db.commit(); db.refresh(image); return image

@app.get("/products/{product_id}/images", response_model=list[ProductImageOut])
def list_product_images(product_id: UUID, db: Session = Depends(get_db)):
    get_or_404(db, Product, product_id)
    return db.scalars(select(ProductImage).where(ProductImage.product_id == product_id).order_by(ProductImage.is_primary.desc(), ProductImage.id)).all()

@app.patch("/product-images/{id}", response_model=ProductImageOut)
def update_product_image(id: UUID, payload: ProductImageIn, db: Session = Depends(get_db)):
    image = get_or_404(db, ProductImage, id)
    if payload.is_primary:
        db.query(ProductImage).filter(ProductImage.product_id == image.product_id, ProductImage.id != id).update({ProductImage.is_primary: False})
    elif image.is_primary:
        replacement = db.scalar(select(ProductImage).where(ProductImage.product_id == image.product_id, ProductImage.id != id).order_by(ProductImage.id))
        if replacement: replacement.is_primary = True
        else: payload.is_primary = True
    for key, value in payload.model_dump().items(): setattr(image, key, value)
    db.commit(); db.refresh(image); return image

@app.delete("/product-images/{id}", status_code=204)
def delete_product_image(id: UUID, db: Session = Depends(get_db)):
    image = get_or_404(db, ProductImage, id)
    replacement = None
    if image.is_primary:
        replacement = db.scalar(select(ProductImage).where(ProductImage.product_id == image.product_id, ProductImage.id != id).order_by(ProductImage.id))
    db.delete(image); db.flush()
    if replacement: replacement.is_primary = True
    db.commit()

@app.post("/addresses", response_model=AddressOut, status_code=201)
def create_address(payload: AddressIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.is_default:
        db.query(Address).filter(Address.user_id == current_user.id).update({Address.is_default: False})
    elif not db.scalar(select(Address.id).where(Address.user_id == current_user.id)):
        payload.is_default = True
    obj = Address(user_id=current_user.id, **payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj); return obj

@app.get("/addresses", response_model=list[AddressOut])
def list_addresses(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Address).where(Address.user_id == current_user.id).order_by(Address.is_default.desc(), Address.created_at.desc())).all()

@app.get("/addresses/{id}", response_model=AddressOut)
def get_address(id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    address = get_or_404(db, Address, id); require_user_id(address.user_id, current_user); return address

@app.patch("/addresses/{id}", response_model=AddressOut)
def update_address(id: UUID, payload: AddressIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    address = get_or_404(db, Address, id); require_user_id(address.user_id, current_user)
    if payload.is_default:
        db.query(Address).filter(Address.user_id == current_user.id, Address.id != id).update({Address.is_default: False})
    elif address.is_default:
        replacement = db.scalar(select(Address).where(Address.user_id == current_user.id, Address.id != id).order_by(Address.created_at.desc()))
        if replacement: replacement.is_default = True
        else: payload.is_default = True
    for key, value in payload.model_dump().items(): setattr(address, key, value)
    db.commit(); db.refresh(address); return address

@app.delete("/addresses/{id}", status_code=204)
def delete_address(id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    address = get_or_404(db, Address, id); require_user_id(address.user_id, current_user)
    was_default = address.is_default
    db.delete(address); db.flush()
    if was_default:
        replacement = db.scalar(select(Address).where(Address.user_id == current_user.id).order_by(Address.created_at.desc()))
        if replacement: replacement.is_default = True
    db.commit()

@app.post("/cart", response_model=CartOut, status_code=201)
def add_to_cart(payload: CartIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_user_id(payload.user_id, current_user)
    get_or_404(db, User, payload.user_id); get_or_404(db, Product, payload.product_id)
    obj = db.scalar(select(Cart).where(Cart.user_id == payload.user_id, Cart.product_id == payload.product_id))
    if obj: obj.quantity += payload.quantity
    else: obj = Cart(**payload.model_dump()); db.add(obj)
    db.commit(); db.refresh(obj); return obj

@app.get("/cart", response_model=list[CartOut])
def list_cart(user_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_user_id(user_id, current_user)
    return db.scalars(select(Cart).where(Cart.user_id == user_id)).all()

@app.patch("/cart/{id}", response_model=CartOut)
def update_cart(id: UUID, payload: CartUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    obj = get_or_404(db, Cart, id); require_user_id(obj.user_id, current_user)
    obj.quantity = payload.quantity; db.commit(); db.refresh(obj); return obj

@app.delete("/cart/{id}", status_code=204)
def delete_cart(id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    obj = get_or_404(db, Cart, id); require_user_id(obj.user_id, current_user)
    db.delete(obj); db.commit()

@app.post("/orders", response_model=OrderOut, status_code=201)
def create_order(payload: OrderCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_user_id(payload.user_id, current_user)
    get_or_404(db, User, payload.user_id)
    address = get_or_404(db, Address, payload.address_id)
    require_user_id(address.user_id, current_user)
    order_items = []; total = Decimal("0.00")
    for item in payload.items:
        product = get_or_404(db, Product, item.product_id)
        if product.stock_qty < item.quantity: raise HTTPException(400, f"Insufficient stock for {product.name}")
        product.stock_qty -= item.quantity; line = product.price * item.quantity; total += line
        order_items.append(OrderItem(product_id=product.id, quantity=item.quantity, price_at_purchase=product.price))
    order = Order(user_id=payload.user_id, address_id=payload.address_id, total_amount=total, status="pending"); db.add(order); db.flush()
    for item in order_items: item.order_id = order.id; db.add(item)
    db.commit(); db.refresh(order); return order

@app.get("/orders", response_model=list[OrderOut])
def list_orders(user_id: Optional[UUID] = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user_id: require_user_id(user_id, current_user)
    q = select(Order).where(Order.user_id == current_user.id)
    return db.scalars(q.order_by(Order.created_at.desc())).all()

@app.get("/orders/{id}", response_model=OrderOut)
def get_order(id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = get_or_404(db, Order, id); require_order_owner(order, current_user); return order

@app.get("/orders/{id}/items", response_model=list[OrderItemOut])
def list_order_items(id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = get_or_404(db, Order, id); require_order_owner(order, current_user)
    return db.scalars(select(OrderItem).where(OrderItem.order_id == id)).all()

@app.patch("/orders/{id}/status", response_model=OrderOut)
def update_order_status(id: UUID, payload: OrderStatusUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    obj = get_or_404(db, Order, id); require_order_owner(obj, current_user)
    obj.status = payload.status; db.commit(); db.refresh(obj); return obj

@app.delete("/orders/{id}", status_code=204)
def delete_order(id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    obj = get_or_404(db, Order, id); require_order_owner(obj, current_user)
    db.delete(obj); db.commit()

import csv
import io
import os
import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, abort, flash, make_response, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func, or_

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "true" if os.environ.get("RENDER") else "false").lower() == "true"

database_url = os.environ.get("DATABASE_URL", "").strip()
if database_url.startswith("postgres://"):
    database_url = "postgresql://" + database_url[len("postgres://"):]
if database_url:
    # psycopg v3 driver is installed from requirements.txt
    if database_url.startswith("postgresql://") and "+" not in database_url.split("://", 1)[0]:
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["DEMO_STORAGE"] = False
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///maketek.db"
    app.config["DEMO_STORAGE"] = True

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    category = db.Column(db.String(80), nullable=False, default="Outros")
    location = db.Column(db.String(100), nullable=False, default="Armazém principal")
    unit = db.Column(db.String(24), nullable=False, default="un.")
    supplier = db.Column(db.String(160), nullable=False, default="")
    cost = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    price = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    min_stock = db.Column(db.Integer, nullable=False, default=5)
    max_stock = db.Column(db.Integer, nullable=False, default=50)
    notes = db.Column(db.Text, nullable=False, default="")
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

class Movement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    kind = db.Column(db.String(24), nullable=False)
    quantity_delta = db.Column(db.Integer, nullable=False)
    before_qty = db.Column(db.Integer, nullable=False)
    after_qty = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(240), nullable=False, default="")
    reference = db.Column(db.String(100), nullable=False, default="")
    operator = db.Column(db.String(100), nullable=False, default="Administrador")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    product = db.relationship("Product", backref=db.backref("movements", lazy=True))

def configured_login():
    return bool(os.environ.get("ADMIN_USERNAME") and os.environ.get("ADMIN_PASSWORD"))

def logged_in():
    return session.get("maketek_logged_in") is True

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if configured_login() and not logged_in():
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def as_int(value, label, minimum=0):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}: indica um número inteiro válido.")
    if number < minimum:
        raise ValueError(f"{label}: o valor mínimo é {minimum}.")
    return number

def as_money(value, label):
    try:
        number = float(str(value or "0").replace(",", "."))
    except ValueError:
        raise ValueError(f"{label}: indica um valor válido.")
    if number < 0:
        raise ValueError(f"{label}: não pode ser negativo.")
    return round(number, 2)

def record_movement(product, kind, new_qty, reason="", reference="", operator="Administrador"):
    if new_qty < 0:
        raise ValueError("A operação foi recusada: o stock não pode ficar negativo.")
    old_qty = product.quantity
    db.session.add(Movement(
        product=product, kind=kind, quantity_delta=new_qty-old_qty,
        before_qty=old_qty, after_qty=new_qty,
        reason=(reason or "").strip()[:240],
        reference=(reference or "").strip()[:100],
        operator=(operator or "Administrador").strip()[:100],
    ))
    product.quantity = new_qty
    product.updated_at = utcnow()

@app.context_processor
def common_context():
    return {
        "app_currency": os.environ.get("APP_CURRENCY", "AOA").upper(),
        "demo_storage": app.config["DEMO_STORAGE"],
        "auth_enabled": configured_login(),
        "is_logged_in": logged_in(),
    }

@app.template_filter("money")
def money(value):
    try:
        return f"{float(value or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00"

@app.template_filter("dt")
def dt(value):
    return value.strftime("%d/%m/%Y %H:%M") if value else "—"

@app.get("/health")
def health():
    return {"status": "ok", "app": "maketek"}

@app.get("/login")
def login():
    if not configured_login():
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.post("/login")
def login_post():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    expected_user = os.environ.get("ADMIN_USERNAME", "")
    expected_password = os.environ.get("ADMIN_PASSWORD", "")
    if configured_login() and secrets.compare_digest(username, expected_user) and secrets.compare_digest(password, expected_password):
        session.clear()
        session["maketek_logged_in"] = True
        session["operator"] = username[:100]
        flash("Sessão iniciada.", "success")
        target = request.args.get("next", "")
        if not target.startswith("/") or target.startswith("//"):
            target = url_for("dashboard")
        return redirect(target)
    flash("Credenciais incorretas.", "error")
    return redirect(url_for("login"))

@app.post("/logout")
def logout():
    session.clear()
    flash("Sessão terminada.", "success")
    return redirect(url_for("login") if configured_login() else url_for("dashboard"))

@app.get("/")
@login_required
def dashboard():
    term = request.args.get("q", "").strip()[:100]
    category = request.args.get("category", "").strip()[:80]
    status = request.args.get("status", "").strip()
    query = Product.query.filter_by(active=True)
    if term:
        like = f"%{term}%"
        query = query.filter(or_(Product.name.ilike(like), Product.sku.ilike(like), Product.supplier.ilike(like)))
    if category:
        query = query.filter_by(category=category)
    if status == "low":
        query = query.filter(Product.quantity <= Product.min_stock, Product.quantity > 0)
    elif status == "out":
        query = query.filter(Product.quantity == 0)
    elif status == "ok":
        query = query.filter(Product.quantity > Product.min_stock)
    products = query.order_by(Product.name.asc()).limit(300).all()
    all_active = Product.query.filter_by(active=True).all()
    low = [p for p in all_active if p.quantity <= p.min_stock]
    units = sum(p.quantity for p in all_active)
    stock_value = sum(float(p.cost or 0) * p.quantity for p in all_active)
    recent = Movement.query.order_by(Movement.created_at.desc(), Movement.id.desc()).limit(8).all()
    categories = sorted({p.category for p in all_active})
    category_totals = {}
    for p in all_active:
        category_totals[p.category] = category_totals.get(p.category, 0) + p.quantity
    return render_template(
        "dashboard.html", products=products, low=sorted(low, key=lambda p: p.quantity)[:8],
        product_count=len(all_active), units=units, stock_value=stock_value, low_count=len(low),
        recent=recent, categories=categories, category=category, status=status,
        q=term, category_totals=sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:6]
    )

@app.route("/products/new", methods=["GET", "POST"])
@login_required
def product_new():
    if request.method == "POST":
        try:
            sku = request.form.get("sku", "").strip()[:64]
            name = request.form.get("name", "").strip()[:160]
            if not sku or not name:
                raise ValueError("O nome e o SKU são obrigatórios.")
            if Product.query.filter(func.lower(Product.sku) == sku.lower()).first():
                raise ValueError("Já existe um produto com esse SKU.")
            qty = as_int(request.form.get("quantity"), "Quantidade")
            p = Product(
                sku=sku, name=name,
                category=request.form.get("category", "Outros").strip()[:80] or "Outros",
                location=request.form.get("location", "Armazém principal").strip()[:100] or "Armazém principal",
                unit=request.form.get("unit", "un.").strip()[:24] or "un.",
                supplier=request.form.get("supplier", "").strip()[:160],
                cost=as_money(request.form.get("cost"), "Custo"),
                price=as_money(request.form.get("price"), "Preço"),
                quantity=0, min_stock=as_int(request.form.get("min_stock"), "Stock mínimo"),
                max_stock=as_int(request.form.get("max_stock"), "Stock máximo"),
                notes=request.form.get("notes", "").strip()[:2000],
            )
            if p.max_stock < p.min_stock:
                raise ValueError("O stock máximo não pode ser inferior ao mínimo.")
            db.session.add(p)
            db.session.flush()
            if qty:
                record_movement(p, "entrada inicial", qty, "Saldo inicial", "SALDO-INICIAL", session.get("operator", "Demonstração"))
            db.session.commit()
            flash("Produto criado e saldo inicial registado no histórico.", "success")
            return redirect(url_for("dashboard"))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "error")
        except Exception:
            db.session.rollback()
            app.logger.exception("Erro ao criar produto")
            flash("Não foi possível guardar o produto. Verifica os dados e tenta novamente.", "error")
    return render_template("product_form.html", product=None, title="Novo produto")

@app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def product_edit(product_id):
    p = Product.query.get_or_404(product_id)
    if request.method == "POST":
        try:
            sku = request.form.get("sku", "").strip()[:64]
            name = request.form.get("name", "").strip()[:160]
            if not sku or not name:
                raise ValueError("O nome e o SKU são obrigatórios.")
            other = Product.query.filter(func.lower(Product.sku) == sku.lower(), Product.id != p.id).first()
            if other:
                raise ValueError("Esse SKU já pertence a outro produto.")
            p.sku, p.name = sku, name
            p.category = request.form.get("category", "Outros").strip()[:80] or "Outros"
            p.location = request.form.get("location", "").strip()[:100]
            p.unit = request.form.get("unit", "un.").strip()[:24]
            p.supplier = request.form.get("supplier", "").strip()[:160]
            p.cost = as_money(request.form.get("cost"), "Custo")
            p.price = as_money(request.form.get("price"), "Preço")
            p.min_stock = as_int(request.form.get("min_stock"), "Stock mínimo")
            p.max_stock = as_int(request.form.get("max_stock"), "Stock máximo")
            p.notes = request.form.get("notes", "").strip()[:2000]
            if p.max_stock < p.min_stock:
                raise ValueError("O stock máximo não pode ser inferior ao mínimo.")
            db.session.commit()
            flash("Dados do produto atualizados.", "success")
            return redirect(url_for("dashboard"))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "error")
        except Exception:
            db.session.rollback()
            app.logger.exception("Erro ao editar produto")
            flash("Não foi possível atualizar o produto.", "error")
    return render_template("product_form.html", product=p, title="Editar produto")

@app.post("/products/<int:product_id>/archive")
@login_required
def product_archive(product_id):
    p = Product.query.get_or_404(product_id)
    p.active = False
    db.session.commit()
    flash("Produto arquivado; o histórico foi preservado.", "success")
    return redirect(url_for("dashboard"))

@app.route("/products/<int:product_id>/movement", methods=["GET", "POST"])
@login_required
def movement_new(product_id):
    p = Product.query.get_or_404(product_id)
    if request.method == "POST":
        try:
            kind = request.form.get("kind", "")
            amount = as_int(request.form.get("quantity"), "Quantidade", 1)
            if kind == "entrada":
                new_qty = p.quantity + amount
            elif kind == "saida":
                new_qty = p.quantity - amount
            elif kind == "contagem":
                new_qty = amount
            else:
                raise ValueError("Tipo de movimentação inválido.")
            reason = request.form.get("reason", "").strip()
            if kind == "contagem":
                reason = f"Contagem física: {reason}".strip(": ")
            record_movement(p, kind, new_qty, reason, request.form.get("reference", ""), session.get("operator", "Demonstração"))
            db.session.commit()
            flash("Movimentação registada com saldo anterior e posterior.", "success")
            return redirect(url_for("dashboard"))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "error")
        except Exception:
            db.session.rollback()
            app.logger.exception("Erro ao registar movimento")
            flash("Não foi possível registar a movimentação.", "error")
    return render_template("movement_form.html", product=p)

@app.get("/movements")
@login_required
def movements():
    rows = Movement.query.order_by(Movement.created_at.desc(), Movement.id.desc()).limit(500).all()
    return render_template("movements.html", movements=rows)

@app.get("/export/products.csv")
@login_required
def export_products():
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["SKU", "Nome", "Categoria", "Localização", "Unidade", "Fornecedor", "Quantidade", "Stock mínimo", "Stock máximo", "Custo unitário", "Preço unitário", "Ativo", "Observações"])
    for p in Product.query.order_by(Product.name).all():
        writer.writerow([p.sku, p.name, p.category, p.location, p.unit, p.supplier, p.quantity, p.min_stock, p.max_stock, p.cost, p.price, "sim" if p.active else "não", p.notes])
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = 'attachment; filename="maketek-produtos.csv"'
    return response

@app.get("/export/movements.csv")
@login_required
def export_movements():
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Data", "SKU", "Produto", "Tipo", "Variação", "Saldo anterior", "Saldo posterior", "Motivo", "Referência", "Operador"])
    for m in Movement.query.order_by(Movement.created_at.desc()).all():
        writer.writerow([m.created_at.isoformat(sep=" "), m.product.sku, m.product.name, m.kind, m.quantity_delta, m.before_qty, m.after_qty, m.reason, m.reference, m.operator])
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = 'attachment; filename="maketek-movimentacoes.csv"'
    return response

@app.post("/demo")
@login_required
def load_demo():
    if Product.query.count():
        flash("Já existem produtos na base de dados; a demonstração não foi duplicada.", "info")
        return redirect(url_for("dashboard"))
    examples = [
        ("ESC-001","Papel A4 — resma","Escritório","Papelaria Central",42,15,4800),
        ("ELE-024","Toner impressora HP","Eletrónica","Tech Supply",6,8,18500),
        ("LIM-008","Detergente multiusos 5L","Limpeza","LimpaBem",18,6,3200),
        ("BEB-013","Água mineral 1,5L","Bebidas","Distribuidora K",0,24,350),
        ("ESC-016","Caderno A5","Escritório","Papelaria Central",54,20,900),
        ("ELE-032","Rato USB","Eletrónica","Tech Supply",4,5,4200),
        ("MER-007","Café 250g","Mercearia","Distribuidora K",13,10,2800),
        ("LIM-011","Lixívia 1L","Limpeza","LimpaBem",26,8,750),
    ]
    try:
        for sku,name,cat,supplier,qty,min_stock,cost in examples:
            p=Product(sku=sku,name=name,category=cat,supplier=supplier,quantity=0,min_stock=min_stock,max_stock=max(min_stock*3,qty),cost=cost,price=cost*1.25,location="Armazém principal",unit="un.")
            db.session.add(p)
            db.session.flush()
            if qty:
                record_movement(p,"entrada inicial",qty,"Saldo de demonstração","DEMO", "Demonstração")
        db.session.commit()
        flash("Dados de demonstração adicionados.", "success")
    except Exception:
        db.session.rollback()
        app.logger.exception("Erro ao carregar demonstração")
        flash("Não foi possível carregar os dados de demonstração.", "error")
    return redirect(url_for("dashboard"))

@app.errorhandler(400)
def bad_request(_error):
    return render_template("error.html", code=400, message="Pedido inválido ou token de segurança expirado. Atualiza a página e tenta novamente."), 400

@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="Não encontrámos essa página ou produto."), 404

@app.errorhandler(500)
def server_error(_error):
    db.session.rollback()
    return render_template("error.html", code=500, message="Ocorreu um erro inesperado. Consulta os registos do serviço e tenta novamente."), 500

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=False)

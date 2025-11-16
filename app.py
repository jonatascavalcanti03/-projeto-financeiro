# Aplicativo de Organização Financeira Pessoal
# Desenvolvido com Flask + Bootstrap + SQLAlchemy


from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

app = Flask(__name__)

# -----------------------------
# FILTRO PARA FORMATAR DATAS NO HTML
# -----------------------------
@app.template_filter()
def date(value, format='%d/%m/%Y'):
    # Se não tiver data, retorna vazio
    if value is None:
        return ""
    # Formata a data no padrão: dia/mês/ano
    return value.strftime(format)

# -----------------------------
# CONFIGURAÇÃO DO BANCO DE DADOS
# -----------------------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///financas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -----------------------------
# MODELO DA TABELA DE TRANSAÇÕES
# -----------------------------
class Transacao(db.Model):
    __tablename__ = 'transacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    tipo = db.Column(db.String(10), nullable=False)  # Receita ou Despesa
    data = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    categoria = db.Column(db.String(50), nullable=False)

# -----------------------------
# MODELO DA TABELA DE ORÇAMENTOS
# -----------------------------
class Orcamento(db.Model):
    __tablename__ = 'orcamentos'
    
    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(50), unique=True, nullable=False)
    limite = db.Column(db.Float, nullable=False)

# Categorias usadas no sistema
CATEGORIAS_PADRAO = [
    'Alimentação', 'Moradia', 'Transporte', 'Lazer',
    'Saúde', 'Salário', 'Outros'
]

# Meses para filtros
MESES = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio',
    6: 'Junho', 7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro',
    11: 'Novembro', 12: 'Dezembro'
}

# -----------------------------
# CRIA AS TABELAS NO BANCO (SE NÃO EXISTIREM)
# -----------------------------
with app.app_context():
    db.create_all()

    # Garante que cada categoria tenha um orçamento no banco
    for cat in CATEGORIAS_PADRAO:
        if not Orcamento.query.filter_by(categoria=cat).first():
            db.session.add(Orcamento(categoria=cat, limite=0.0))
    db.session.commit()

# -----------------------------
# FUNÇÃO PARA CALCULAR SALDO
# -----------------------------
def calcular_saldo():
    transacoes = Transacao.query.all()
    saldo = 0

    # Soma receitas e subtrai despesas
    for t in transacoes:
        if t.tipo == "Receita":
            saldo += t.valor
        else:
            saldo -= t.valor

    return saldo

# -----------------------------
# FUNÇÃO PARA CALCULAR GASTOS POR CATEGORIA
# -----------------------------
def calcular_gastos_por_categoria():
    orcamentos = Orcamento.query.all()
    
    # Começa com zero em cada categoria
    gastos = {o.categoria: 0 for o in orcamentos}

    despesas = Transacao.query.filter_by(tipo='Despesa').all()

    for t in despesas:
        gastos[t.categoria] += t.valor

    return gastos

# -----------------------------
# PÁGINA PRINCIPAL (DASHBOARD)
# -----------------------------
@app.route('/')
def index():
    ultimas_transacoes = Transacao.query.order_by(
        Transacao.data.desc(),
        Transacao.id.desc()
    ).limit(5).all()

    saldo_atual = calcular_saldo()
    gastos = calcular_gastos_por_categoria()
    orcamentos = Orcamento.query.all()

    resumo = []
    for o in orcamentos:
        gasto = gastos.get(o.categoria, 0)
        resumo.append({
            "categoria": o.categoria,
            "limite": o.limite,
            "gasto": gasto,
            "restante": o.limite - gasto
        })

    # Exibe apenas categorias com limite maior que zero
    resumo = [r for r in resumo if r["limite"] > 0]

    return render_template(
        'index.html',
        saldo_atual=saldo_atual,
        transacoes=ultimas_transacoes,
        now=datetime.now(),
        resumo_orcamento=resumo,
        categorias_orcamento=[o.categoria for o in orcamentos]
    )

# -----------------------------
# PÁGINA DE EXTRATO
# -----------------------------
@app.route('/extrato')
def extrato():
    # Coleta filtros da URL
    categoria = request.args.get("categoria")
    tipo = request.args.get("tipo")
    mes = request.args.get("mes")
    ano = request.args.get("ano")

    query = Transacao.query.order_by(Transacao.data.desc())

    # Aplica filtros um por um
    if categoria and categoria != "Todos":
        query = query.filter_by(categoria=categoria)

    if tipo and tipo != "Todos":
        query = query.filter_by(tipo=tipo)

    if mes and mes.isdigit():
        query = query.filter(func.extract('month', Transacao.data) == int(mes))

    if ano and ano.isdigit():
        query = query.filter(func.extract('year', Transacao.data) == int(ano))

    transacoes = query.all()

    return render_template(
        "extrato.html",
        transacoes=transacoes,
        categorias_orcamento=[o.categoria for o in Orcamento.query.all()],
        meses_disponiveis=MESES
    )

# -----------------------------
# ADICIONAR TRANSAÇÃO
# -----------------------------
@app.route('/adicionar', methods=['POST'])
def adicionar_transacao():
    descricao = request.form.get('descricao')
    valor = float(request.form.get('valor'))
    tipo = request.form.get('tipo')
    data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
    categoria = request.form.get('categoria')

    nova = Transacao(
        descricao=descricao,
        valor=valor,
        tipo=tipo,
        data=data,
        categoria=categoria
    )

    db.session.add(nova)
    db.session.commit()

    return redirect(url_for('index'))

# -----------------------------
# PÁGINA DE ORÇAMENTO
# -----------------------------
@app.route('/orcamento')
def orcamento_page():
    orcamentos = Orcamento.query.all()
    return render_template(
        'orcamento.html',
        orcamentos={o.categoria: o.limite for o in orcamentos},
        categorias_padrao=CATEGORIAS_PADRAO
    )

# -----------------------------
# SALVAR ORÇAMENTO
# -----------------------------
@app.route('/salvar_orcamento', methods=['POST'])
def salvar_orcamento():
    for cat in CATEGORIAS_PADRAO:
        valor = request.form.get(cat)
        valor = float(valor) if valor else 0

        orc = Orcamento.query.filter_by(categoria=cat).first()
        orc.limite = valor

    db.session.commit()
    return redirect(url_for('index'))

# -----------------------------
# EXCLUIR UMA TRANSAÇÃO
# -----------------------------
@app.route('/excluir/<int:id>', methods=['POST'])
def excluir(id):
    transacao = Transacao.query.get_or_404(id)
    db.session.delete(transacao)
    db.session.commit()
    return redirect(url_for('extrato'))

# -----------------------------
# FORMULÁRIO DE EDIÇÃO
# -----------------------------
@app.route('/editar/<int:id>', methods=['GET'])
def editar_form(id):
    return render_template(
        "editar.html",
        transacao=Transacao.query.get_or_404(id),
        categorias_orcamento=[o.categoria for o in Orcamento.query.all()]
    )

# -----------------------------
# SALVAR ALTERAÇÕES DE EDIÇÃO
# -----------------------------
@app.route('/editar/<int:id>', methods=['POST'])
def editar_salvar(id):
    t = Transacao.query.get_or_404(id)

    t.descricao = request.form.get('descricao')
    t.valor = float(request.form.get('valor'))
    t.tipo = request.form.get('tipo')
    t.data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
    t.categoria = request.form.get('categoria')

    db.session.commit()
    return redirect(url_for('extrato'))

# -----------------------------
# RODAR O SERVIDOR
# -----------------------------
if __name__ == '__main__':
    app.run(debug=True)

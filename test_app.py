import pytest
from app import app, DatabaseModel, CupcakeModel, PedidoModel

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_conexao_e_listagem_produtos():
    """Valida se a base de dados devolve cupcakes com stock."""
    produtos = CupcakeModel.listar_todos()
    assert len(produtos) > 0
    assert "preco" in produtos[0]
    assert "nome" in produtos[0]

def test_rota_home_sucesso(client):
    """Garante que a página inicial carrega com código HTTP 200."""
    resposta = client.get('/')
    assert resposta.status_code == 200
    assert b"Sweet Cupcake Gourmet" in resposta.data

def test_bloqueio_pedido_sem_itens(client):
    """Valida a regra de negócio que rejeita encomendas com carrinho vazio."""
    payload = {
        "nome": "Cliente Teste",
        "email": "teste@exemplo.com",
        "telefone": "61999999999",
        "endereco": "Endereço Teste",
        "forma_pagamento": "PIX",
        "itens": []
    }
    resposta = client.post('/api/checkout', json=payload)
    assert resposta.status_code == 400
    dados = resposta.get_json()
    assert dados["sucesso"] is False

def test_bloqueio_campos_obrigatorios_vazios(client):
    """Garante que dados incompletos não avançam para o banco."""
    payload = {
        "nome": "",
        "email": "invalido@teste.com",
        "telefone": "",
        "endereco": "",
        "forma_pagamento": "PIX",
        "itens": [{"id": 1, "quantidade": 1}]
    }
    resposta = client.post('/api/checkout', json=payload)
    assert resposta.status_code == 400
    dados = resposta.get_json()
    assert dados["sucesso"] is False

def test_retorno_checkout_com_mock_e_cliente(client):
    """Garante que a API de checkout retorna nome_cliente e forma_pagamento para o Mock."""
    payload = {
        "nome": "Arthur Teste",
        "email": "arthur@exemplo.com",
        "telefone": "61999999999",
        "endereco": "Rua Teste, 100",
        "forma_pagamento": "PIX",
        "itens": [{"id": 1, "quantidade": 1}]
    }
    resposta = client.post('/api/checkout', json=payload)
    assert resposta.status_code == 201
    dados = resposta.get_json()
    assert dados["sucesso"] is True
    assert dados["nome_cliente"] == "Arthur Teste"
    assert dados["forma_pagamento"] == "PIX"

def test_rota_confirmacao_com_mock_pix(client):
    """Valida se confirmacao renderiza o nome do cliente e os dados do Mock PIX."""
    resposta = client.get('/confirmacao?nome=Arthur%20Teste&pagamento=PIX')
    assert resposta.status_code == 200
    assert b"Arthur Teste" in resposta.data
    assert b"Gateway Simulado (Mock)" in resposta.data
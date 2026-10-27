import pyodbc
import uuid
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DB_CONFIG = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=localhost;"  
    "Database=CupcakeGourmetDB;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

class DatabaseModel:
    @staticmethod
    def get_connection():
        return pyodbc.connect(DB_CONFIG)

class CupcakeModel:
    @staticmethod
    def listar_todos():
        conn = DatabaseModel.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome, descricao, preco, imagem_url, estoque FROM produtos WHERE estoque > 0")
        colunas = [col[0] for col in cursor.description]
        produtos = [dict(zip(colunas, row)) for row in cursor.fetchall()]
        conn.close()
        return produtos

class PedidoModel:
    @staticmethod
    def processar_pedido(nome, email, telefone, endereco, forma_pagamento, itens):
        if not itens:
            raise ValueError("O carrinho não pode estar vazio.")

        conn = DatabaseModel.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT id FROM clientes WHERE email = ?", (email,))
            cliente = cursor.fetchone()

            if cliente:
                cliente_id = cliente[0]
                cursor.execute("""
                    UPDATE clientes SET nome = ?, telefone = ?, endereco = ? WHERE id = ?
                """, (nome, telefone, endereco, cliente_id))
            else:
                cursor.execute("""
                    INSERT INTO clientes (nome, email, telefone, endereco)
                    OUTPUT INSERTED.id
                    VALUES (?, ?, ?, ?)
                """, (nome, email, telefone, endereco))
                cliente_id = cursor.fetchone()[0]

            total_pedido = 0.0
            itens_processados = []

            for item in itens:
                p_id = int(item['id'])
                qtd = int(item['quantidade'])
                if qtd <= 0:
                    continue

                cursor.execute("SELECT preco, estoque FROM produtos WHERE id = ?", (p_id,))
                prod = cursor.fetchone()
                if not prod or prod[1] < qtd:
                    raise ValueError(f"Stock insuficiente para o produto ID {p_id}.")

                preco_unit = float(prod[0])
                total_pedido += preco_unit * qtd
                itens_processados.append((p_id, qtd, preco_unit))

        
            cursor.execute("""
                INSERT INTO pedidos (cliente_id, forma_pagamento, total)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?)
            """, (cliente_id, forma_pagamento, total_pedido))
            pedido_id = cursor.fetchone()[0]

            for p_id, qtd, preco_unit in itens_processados:
                cursor.execute("""
                    INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_unitario)
                    VALUES (?, ?, ?, ?)
                """, (pedido_id, p_id, qtd, preco_unit))

                cursor.execute("""
                    UPDATE produtos SET estoque = estoque - ? WHERE id = ?
                """, (qtd, p_id))

            conn.commit()
            return pedido_id, total_pedido

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()


@app.route("/")
def home():
    cupcakes = CupcakeModel.listar_todos()
    return render_template("index.html", cupcakes=cupcakes)

@app.route("/api/checkout", methods=["POST"])
def checkout():
    dados = request.get_json()
    try:
        nome = dados.get("nome", "").strip()
        email = dados.get("email", "").strip()
        telefone = dados.get("telefone", "").strip()
        endereco = dados.get("endereco", "").strip()
        forma_pagamento = dados.get("forma_pagamento", "")
        itens = dados.get("itens", [])

        if not all([nome, email, telefone, endereco, forma_pagamento]):
            return jsonify({"sucesso": False, "mensagem": "Preencha todos os campos obrigatórios."}), 400

        pedido_id, total = PedidoModel.processar_pedido(
            nome, email, telefone, endereco, forma_pagamento, itens
        )
        return jsonify({
            "sucesso": True,
            "pedido_id": pedido_id,
            "nome_cliente": nome,
            "forma_pagamento": forma_pagamento,
            "total": f"R$ {total:.2f}"
        }), 201

    except ValueError as ve:
        return jsonify({"sucesso": False, "mensagem": str(ve)}), 400
    except Exception as e:
        return jsonify({"sucesso": False, "mensagem": "Erro interno ao processar a encomenda."}), 500

@app.route("/confirmacao")
def confirmacao():
    nome_cliente = request.args.get("nome", "Cliente")
    forma_pagamento = request.args.get("pagamento", "PIX").upper()
    
    dados_mock = {
        "metodo": forma_pagamento,
        "detalhes": {}
    }
    
    if "PIX" in forma_pagamento:
        codigo_pix = f"00020126580014br.gov.bcb.pix0136{uuid.uuid4()}5204000053039865802BR5913SWEET CUPCAKE6008BRASILIA62070503***6304"
        dados_mock["detalhes"] = {
            "qr_code_url": "https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=PagamentoSimuladoSweetCupcake",
            "copia_cola": codigo_pix
        }
    elif "BOLETO" in forma_pagamento:
        linha_digitavel = f"34191.79001 01043.510047 {uuid.uuid4().hex[:10].upper()} 1 99990000000000"
        dados_mock["detalhes"] = {
            "linha_digitavel": linha_digitavel,
            "vencimento": "Em até 3 dias úteis"
        }
    else:  # Cartão de Crédito
        dados_mock["detalhes"] = {
            "status_transacao": "Autorizada com Sucesso",
            "bandeira": "Mastercard / Visa (Simulação)",
            "codigo_autorizacao": f"AUTH-{uuid.uuid4().hex[:6].upper()}"
        }
        
    return render_template("pedido_sucesso.html", nome_cliente=nome_cliente, mock=dados_mock)


if __name__ == "__main__":
    print("Aceda em: http://127.0.0.1:5000")
    app.run(debug=True)
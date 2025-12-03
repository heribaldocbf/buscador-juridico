import os
from sqlalchemy import create_engine, text

# Pega a string de conexão das "Variáveis de Ambiente" (segredo do GitHub)
db_connection_string = os.environ.get("DB_CONNECTION_STRING")

if not db_connection_string:
    raise ValueError("A variável de ambiente DB_CONNECTION_STRING não foi encontrada.")

print("Iniciando conexão de manutenção...")

try:
    # Conecta ao banco
    engine = create_engine(db_connection_string)
    
    # Executa uma consulta muito leve (apenas pede o horário atual)
    with engine.connect() as connection:
        result = connection.execute(text("SELECT NOW()")).fetchone()
        print(f"Ping realizado com sucesso! Horário do banco: {result[0]}")

except Exception as e:
    print(f"Erro ao conectar: {e}")
    # Opcional: fazer o script falhar para o GitHub avisar por email
    raise e
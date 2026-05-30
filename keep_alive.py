from sqlalchemy import create_engine, text
from db_config import get_db_connection_string

db_connection_string = get_db_connection_string()

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
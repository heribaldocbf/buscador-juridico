from sqlalchemy import text
from db_config import create_db_engine

engine = create_db_engine()

with engine.connect() as conn:
    conn.execute(text("COMMIT")) # Garante que não está em transação
    try:
        # Tenta adicionar a coluna. Se já existir, vai dar erro (e ignoramos)
        conn.execute(text('ALTER TABLE temas_stf ADD COLUMN IF NOT EXISTS "data_ultima_alteracao" TIMESTAMP'))
        print("✅ Coluna 'data_ultima_alteracao' criada com sucesso!")
    except Exception as e:
        print(f"Aviso (pode ignorar se a coluna já existe): {e}")
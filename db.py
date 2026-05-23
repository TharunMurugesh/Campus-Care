import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'campus_tickets_db'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres'),
        port=os.getenv('DB_PORT', '5432')
    )
    return conn

def execute_query(query, params=None, fetch=False, fetchall=False, commit=False):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            
            result = None
            if fetch:
                if fetchall:
                    result = cur.fetchall()
                else:
                    result = cur.fetchone()
            
            if commit:
                conn.commit()
                
            return result
    except Exception as e:
        if commit:
            conn.rollback()
        raise e
    finally:
        conn.close()

import sys
import os

# Add backend to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.dependencies import get_mysql_inspector

if __name__ == "__main__":
    try:
        inspector = get_mysql_inspector()
        tables = inspector.get_table_names()
        print(f"Tables in MySQL: {tables}")
    except Exception as e:
        print(f"Error: {e}")

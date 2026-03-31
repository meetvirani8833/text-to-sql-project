import pymysql
import sys

try:
    print("Attempting to connect to MySQL directly via pymysql...")
    connection = pymysql.connect(
        host='13.203.58.105',
        user='erp_intern',
        password='Interns#2025',
        port=3306,
        connect_timeout=10
    )
    print("✅ SUCCESS: Connected to MySQL!")
    connection.close()
except pymysql.err.OperationalError as e:
    print(f"❌ CONNECTION FAILED: {e}")
    if e.args[0] == 1045:
        print("\nPossible Causes:")
        print("1. Password 'Interns@2025' is incorrect.")
        print("2. Your IP Address is not whitelisted.")
        print(f"   (Error message usually confirms the IP: {e.args[1]})")
except Exception as e:
    print(f"❌ UNEXPECTED ERROR: {e}")

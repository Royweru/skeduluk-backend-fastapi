import subprocess
import os
from pathlib import Path

def setup_alembic():
    """
    Automated setup script for Alembic migrations
    Run this once to initialize your migration system
    """
    print("=" * 60)
    print("ALEMBIC SETUP WIZARD")
    print("=" * 60)
    
    # Step 1: Install Alembic
    print("\n1. Installing Alembic...")
    try:
        subprocess.run(["pip", "install", "alembic"], check=True)
        print("✅ Alembic installed")
    except subprocess.CalledProcessError:
        print("❌ Failed to install Alembic")
        return
    
    # Step 2: Initialize Alembic
    print("\n2. Initializing Alembic...")
    if not Path("alembic").exists():
        try:
            subprocess.run(["alembic", "init", "alembic"], check=True)
            print("✅ Alembic initialized")
        except subprocess.CalledProcessError:
            print("❌ Failed to initialize Alembic")
            return
    else:
        print("⚠️  Alembic directory already exists, skipping...")
    
    # Step 3: Update env.py
    print("\n3. Configuring env.py for async support...")
    env_py_path = Path("alembic/env.py")
    
    if env_py_path.exists():
        with open(env_py_path, 'w') as f:
            f.write(ENV_PY_TEMPLATE)
        print("✅ env.py configured")
    
    # Step 4: Update alembic.ini
    print("\n4. Updating alembic.ini...")
    ini_path = Path("alembic.ini")
    
    if ini_path.exists():
        with open(ini_path, 'r') as f:
            content = f.read()
        
        # Comment out the sqlalchemy.url line
        content = content.replace(
            'sqlalchemy.url = driver://user:pass@localhost/dbname',
            '# sqlalchemy.url = driver://user:pass@localhost/dbname  # Set via env.py'
        )
        
        with open(ini_path, 'w') as f:
            f.write(content)
        print("✅ alembic.ini updated")
    
    # Step 5: Create initial migration
    print("\n5. Creating initial migration...")
    print("⚠️  Make sure your database has existing tables!")
    response = input("Do you have tables in your database? (y/n): ").lower()
    
    if response == 'y':
        try:
            subprocess.run([
                "alembic", "revision", "--autogenerate", 
                "-m", "initial_schema"
            ], check=True)
            print("✅ Initial migration created")
            
            print("\n6. Marking existing database as migrated...")
            subprocess.run(["alembic", "stamp", "head"], check=True)
            print("✅ Database stamped with current version")
        except subprocess.CalledProcessError:
            print("❌ Failed to create migration")
            return
    else:
        print("ℹ️  Run migrations manually after setting up your database")
    
    print("\n" + "=" * 60)
    print("✅ ALEMBIC SETUP COMPLETE!")
    print("=" * 60)
    print("\n📚 Next steps:")
    print("1. When you change models: alembic revision --autogenerate -m 'description'")
    print("2. Apply migrations: alembic upgrade head")
    print("3. Rollback: alembic downgrade -1")
    print("4. Check status: alembic current")
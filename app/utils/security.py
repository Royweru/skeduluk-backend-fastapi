import hashlib
import bcrypt

def get_password_hash(password: str) -> str:
    """Hash password using bcrypt directly"""
    # Pre-hash with SHA256 to handle any length password
    password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    # Hash with bcrypt
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_hash.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using bcrypt directly"""
    # Pre-hash with SHA256 (same as get_password_hash)
    password_hash = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()
    # Verify with bcrypt
    return bcrypt.checkpw(
        password_hash.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )

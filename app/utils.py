from passlib.hash import argon2

def hash(password: str) -> str:
    return argon2.hash(password)

 
def verify(plain_password, hashed_password):
    return argon2.verify(plain_password, hashed_password)
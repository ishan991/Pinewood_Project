from pwdlib import PasswordHash


# Create password hashing object
password_hash = PasswordHash.recommended()


# Users available in our API
users = {

    "admin": {
        "username": "admin",
        "hashed_password": password_hash.hash("admin123"),
        "role": "admin",
    },

    "analyst": {
        "username": "analyst",
        "hashed_password": password_hash.hash("analyst123"),
        "role": "analyst",
    }

}
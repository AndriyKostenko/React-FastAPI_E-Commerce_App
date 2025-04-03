class MockSettings:
    SECRET_KEY = "test_secret"
    ALGORITHM = "HS256"
    TIME_DELTA_MINUTES = 30
    TOKEN_URL = "token"

class MockAuthenticationManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MockAuthenticationManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.secret_key = MockSettings.SECRET_KEY
            self.algorithm = MockSettings.ALGORITHM
            self.token_expire_minutes = MockSettings.TIME_DELTA_MINUTES

def test_singleton():
    # Create two instances
    auth1 = MockAuthenticationManager()
    auth2 = MockAuthenticationManager()
    
    # Test if they are the same instance
    print("Are instances the same?:", auth1 is auth2)
    
    # Test if attributes are the same
    print("Secret key same?:", auth1.secret_key == auth2.secret_key)

# if __name__ == "__main__":
test_singleton()
class RateLimiterError(Exception):

    def __init__(self, detail: dict):
        super().__init__(detail)
    


class RateLimitExceededError(RateLimiterError):
    pass
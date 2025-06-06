class CategoryCreationError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class CategoryNotFoundError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message

class CategoryUpdateError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message
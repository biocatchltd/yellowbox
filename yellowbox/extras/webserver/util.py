class WhyNot(str):
    @classmethod
    def is_ne(cls, field: str, expected, got):
        return cls(f'{field} mismatch: expected {expected}, got {got}')

    def __bool__(self):
        return False

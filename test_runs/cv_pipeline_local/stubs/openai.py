class OpenAI:
    def __init__(self, *args, **kwargs):
        self.chat = _Chat()


class _Chat:
    def __init__(self):
        self.completions = _Completions()


class _Completions:
    def create(self, *args, **kwargs):
        raise RuntimeError("OpenAI calls are disabled in local smoke tests")

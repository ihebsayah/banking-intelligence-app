"""
tests/conftest.py
Installs stub modules for redis + asyncpg so execution_agent code can be
imported without Docker dependencies. Each test file adds its own service
path at index 0 — conftest does NOT add multiple service roots (name collision
with models.py across services).
"""
import sys
import types

# ── Stub: redis ───────────────────────────────────────────────────────────────
if "redis" not in sys.modules:
    redis_mod = types.ModuleType("redis")
    asyncio_mod = types.ModuleType("redis.asyncio")

    class _FakeRedis:
        async def get(self, key): return None
        async def set(self, key, val, ex=None): pass
        async def delete(self, *keys): pass
        async def flushdb(self): pass
        async def keys(self, pattern="*"): return []
        async def close(self): pass

    asyncio_mod.Redis = _FakeRedis
    asyncio_mod.from_url = lambda url, **kw: _FakeRedis()
    redis_mod.asyncio = asyncio_mod
    sys.modules["redis"] = redis_mod
    sys.modules["redis.asyncio"] = asyncio_mod

# ── Stub: asyncpg ─────────────────────────────────────────────────────────────
if "asyncpg" not in sys.modules:
    asyncpg_mod = types.ModuleType("asyncpg")

    class _FakePool:
        async def acquire(self): return self
        async def release(self, conn): pass
        async def close(self): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def fetch(self, sql, *args): return []

    async def _fake_create_pool(*a, **kw): return _FakePool()
    asyncpg_mod.create_pool = _fake_create_pool
    asyncpg_mod.Pool = _FakePool
    sys.modules["asyncpg"] = asyncpg_mod

# ── Stub: spacy (optional — intent_agent loads it lazily) ─────────────────────
if "spacy" not in sys.modules:
    spacy_mod = types.ModuleType("spacy")

    class _FakeTok:
        """Mimics a spaCy Token — iterable by NLP pipeline code."""
        def __init__(self, text):
            self.text = text
            self.is_alpha = text.isalpha()
            self.is_punct = not text.isalpha() and not text.isdigit()
            self.is_digit = text.isdigit()
            self.is_stop = text.lower() in {
                "the", "a", "an", "by", "in", "of", "and", "or", "with",
                "for", "to", "from", "is", "are", "at", "me", "show", "i",
            }
            self.lemma_ = text.lower()
            self.lower_ = text.lower()
            self.pos_ = "NOUN" if text.isalpha() else "PUNCT"
            self.tag_ = "NN"
            self.ent_type_ = ""

    class _FakeDoc:
        """Mimics a spaCy Doc — iterable, has .ents."""
        def __init__(self, text):
            self._tokens = [_FakeTok(w) for w in text.split()]
            self.ents = []

        def __iter__(self):
            return iter(self._tokens)

        def __len__(self):
            return len(self._tokens)

    class _FakeNLP:
        def __call__(self, text):
            return _FakeDoc(text)

    def _load(model, **kw):
        return _FakeNLP()

    spacy_mod.load = _load
    sys.modules["spacy"] = spacy_mod

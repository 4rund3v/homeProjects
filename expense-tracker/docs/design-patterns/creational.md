# Creational Patterns — and when they're ceremony

> Creational patterns are about *how objects get made*, not how they behave. In a
> Django/DRF codebase, most of them are already partly in the framework. The L5/L6
> skill is knowing which to use, which the framework already does, and which to
> deliberately skip.

---

## 1. Simple Factory vs Factory Method

**Simple Factory** — a function that decides which concrete type to return:

```python
def make_source(kind: str, **kw):
    if kind == "card":
        return CardSource(**kw)
    if kind == "bank":
        return BankSource(**kw)
    raise ValueError(kind)
```

**Factory Method** — the "which" decision lives inside a parent class, so a
subsystem creates its own objects without callers knowing the concrete types. In
Python this usually just means an abstract class with a method:

```python
class EventProducer(ABC):
    @abstractmethod
    def build(self, event) -> str: ...

class KafkaEventProducer(EventProducer): ...
class OutboxEventProducer(EventProducer): ...
```

**When to use here:** creating `Money` from raw user input, or choosing which
producer/relay implementation to build based on config. That's a Simple Factory.

**When it's ceremony:** a factory that always returns the same concrete class. If
`make_source("card")` is the *only* call site, just use the constructor directly.
Factories earn their keep when the "which" decision is *data-driven* or *swappable*.

**DRF note:** `get_serializer_class()` is a factory method — the viewset picks the
serializer per route. You're already using one.

---

## 2. Builder

**Problem:** an object with many optional fields, where the positional constructor
becomes unreadable:

```python
Producer(host, port, topic, schema_registry, ...?, ..., batch_size, ...)
```

**Solution:** a builder (or, in Python, just kwargs + a config dataclass):

```python
@dataclass
class ProducerConfig:
    host: str
    topic: str
    batch_size: int = 250
    acks: str = "all"

def make_producer(cfg: ProducerConfig) -> Producer: ...
```

**When to use here:** the Kafka producer, which has ~15 knobs. Python's answer is
usually "a config object," not a fluent builder chain. The *fluent*
`builder.with_x().with_y().build()` style is a Java habit; in Python it's fine but
rarely better than a dataclass.

**When it's ceremony:** building a 3-field object with a builder. Just use kwargs.

---

## 3. Abstract Factory

**Problem:** create a *family* of related objects (a window, a button, a cursor — all
the "Qt" versions, or all the "GTK" versions) and swap the whole family at once.

**In this project: almost never.** You don't have a family of related abstractions
whose implementations you'd swap in unison. The closest analogue — "use Postgres
repository + Postgres connection pool + Postgres migrations" vs "use SQLite for
tests" — is better handled by a single config choice (settings module), not an
Abstract Factory.

**Interview note:** knowing that Abstract Factory exists but recognizing it's the
rarest one in practice is more useful than memorizing it.

---

## 4. Singleton

**The anti-pattern you should mostly avoid.** A globally-accessible single instance:

```python
class _Db:
    _instance = None
    def get(cls): ...   # global access anywhere
```

**Why it's a problem:** it hides the dependency. Your domain service now talks to a
global `_Db` instead of an injected `db`. Testing it means resetting global state,
and two parts of the app that "use the DB" can't use different connections.

**The right shape:** the *component* is a singleton (one DB pool for the process),
but it's **injected** at the app boundary (Django settings / DI container / passed
into the service), not accessed as a global:

```python
class ExpenseService:
    def __init__(self, outbox: OutboxWriter, producer: EventProducer): ...
# the process wires up ONE outbox + ONE producer; the service just receives them
```

**DRF/Django note:** the ORM connection pool and settings are *effectively*
singletons managed by the framework. Don't build more on top of them.

---

## The creational decision table

| Pattern | Use here? | Trigger |
|---------|-----------|---------|
| Simple Factory | Yes | data-driven type choice, one `Money` builder, producer selection |
| Factory Method | Sometimes | a swappable family of producers/relays |
| Builder / Config object | Yes | many-knob objects (Kafka producer) |
| Abstract Factory | Rarely | a whole swappable family you don't have |
| Singleton | Avoid | inject instead; let Django own the framework singletons |

**The L5/L6 framing:** "I prefer injection over singletons; factories only when the
decision is data-driven; and I notice DRF already gives me a Factory Method
(`get_serializer_class`) and Django gives me managed singletons, so I don't
reimplement them."

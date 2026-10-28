"""symbols: regex symbol extraction per language, config flattening per format, manifests, skip rules."""

from __future__ import annotations

from untangle.ingest.symbols import (
    config_format,
    extract_config_keys,
    extract_symbols,
    flatten,
    is_config_path,
    is_doc_path,
    is_noisy_config,
    languages,
    literal_value,
    logical_name,
    parse_config,
    parse_dependencies,
    should_skip,
)

GO = """package main

const retryLimit = 3
const (
\tMaxRetries = 5
\tMode       = iota
)

type Mailer struct {
\thost string
}

type Sender interface {
\tSend() error
}

func NewMailer(host string) *Mailer { return nil }

func (m *Mailer) Send(msg string) error { return nil }

func Generic[T any](x T) T { return x }
"""
PY = """MAX_RETRIES = 3
RETRY_LIMIT: int = 7
lower = 2

class Mailer(Base):
    def send(self, msg):
        pass

async def main():
    pass
"""
TS = """export const retryLimit = 3;
const name = "listmonk";
export const router = createRouter({});
export const handler = async (req: Request) => {};
export default function App() {}
export class Store {
  fetchAll(): Promise<void> {
    return;
  }
}
interface Props {}
export type Row = {};
"""
RS = """pub const MAX_RETRIES: u32 = 3;
pub struct Mailer {}
pub enum Mode { A, B }
pub trait Send {}
pub fn new() -> Mailer { Mailer {} }
impl Mailer {
    pub fn send(&self) {}
}
"""
JAVA = """public class Mailer extends Base {
    public static final int MAX_RETRIES = 3;
    public void send(String msg) {
        if (true) {
        }
    }
}
interface Sender {}
"""
KT = """const val MAX_RETRIES = 3
class Mailer(val host: String) {
    fun send(msg: String): Boolean = true
}
fun main() {}
"""
VUE = """<template><div>{{ x }}</div></template>
<script>
export const pageSize = 20;
export default function setup() {}
</script>
"""


def names(path: str, text: str) -> list[tuple[str, str]]:
    syms, _ = extract_symbols(path, text)
    return [(s.name, s.kind) for s in syms]


def test_go_symbols_and_constants():
    syms, keys = extract_symbols("cmd/mailer.go", GO)
    assert [(s.name, s.kind) for s in syms] == [
        ("retryLimit", "const"), ("MaxRetries", "const"), ("Mailer", "class"), ("Sender", "type"), ("NewMailer", "function"),
        ("Send", "method"), ("Generic", "function"),
    ]
    assert [(k.key, k.value) for k in keys] == [("retryLimit", "3"), ("MaxRetries", "5")]
    assert next(s for s in syms if s.name == "Send").line == 19


def test_python_typescript_rust_java_kotlin_vue():
    assert names("a.py", PY) == [("MAX_RETRIES", "const"), ("RETRY_LIMIT", "const"), ("Mailer", "class"), ("send", "method"), ("main", "function")]
    assert names("a.ts", TS) == [
        ("retryLimit", "const"), ("name", "const"), ("router", "const"), ("handler", "function"), ("App", "function"), ("Store", "class"),
        ("fetchAll", "method"), ("Props", "type"), ("Row", "type"),
    ]
    assert names("a.rs", RS) == [("MAX_RETRIES", "const"), ("Mailer", "class"), ("Mode", "type"), ("Send", "type"), ("new", "function"), ("send", "method")]
    assert names("A.java", JAVA) == [("Mailer", "class"), ("MAX_RETRIES", "const"), ("send", "method"), ("Sender", "type")]
    assert names("a.kt", KT) == [("MAX_RETRIES", "const"), ("Mailer", "class"), ("send", "method"), ("main", "function")]
    assert names("App.vue", VUE) == [("pageSize", "const"), ("setup", "function")]
    _, keys = extract_symbols("a.py", PY)
    assert [(k.key, k.value) for k in keys] == [("MAX_RETRIES", "3"), ("RETRY_LIMIT", "7")]
    assert extract_symbols("notes.txt", "def x():") == ([], [])


def test_literal_values():
    assert literal_value("3") == "3" and literal_value('"a b"') == "a b" and literal_value("True") == "true"
    assert literal_value("None") == "null" and literal_value("3 // comment") == "3" and literal_value("foo()") is None


def test_flatten_and_formats():
    data = {"app": {"retry_limit": 3, "hosts": ["a", "b"], "deep": {"x": {"y": {"z": 1}}}, "servers": [{"host": "a"}], "on": True}}
    assert flatten(data) == {"app.retry_limit": "3", "app.hosts": "a, b", "app.on": "true"}
    assert parse_config("config/app.yaml", "app:\n  retry_limit: 3\n---\nother: 1\n") == {"0.app.retry_limit": "3", "1.other": "1"}
    assert parse_config("config.toml.sample", '[app]\nconcurrency = 10\n[db]\nhost = "localhost"\n') == {"app.concurrency": "10", "db.host": "localhost"}
    assert parse_config(".env.example", 'FOO=bar\nexport BAZ="q u x" # c\n# comment\nQUX=1 # t\n') == {"FOO": "bar", "BAZ": "q u x", "QUX": "1"}
    assert parse_config("setup.cfg", "[flake8]\nmax-line-length = 120\n") == {"flake8.max-line-length": "120"}
    assert parse_config("Dockerfile", 'FROM x\nENV A=1 B="two words"\nARG C=3\n') == {"A": "1", "B": "two words", "C": "3"}
    assert parse_config("x.json", '{"a": {"b": 1}, "d": null, "e": true}') == {"a.b": "1", "d": "null", "e": "true"}
    assert parse_config("x.json", "{not json") == {}
    assert parse_config("x.yaml", "- just\n- a list\n") == {}
    assert config_format("docker-compose.yml") == "yaml" and config_format("app.yaml.dist") == "yaml" and config_format("main.go") is None
    assert logical_name("config.toml.sample") == "config.toml" and logical_name(".env.example") == ".env"


def test_extract_config_keys_skips_translations():
    assert extract_config_keys("i18n/en.json", '{"hello": "world"}') == []
    assert [(k.key, k.value) for k in extract_config_keys("config.yaml", "a: 1\n")] == [("a", "1")]


def test_dependencies():
    go = "module x\n\ngo 1.21\n\nrequire (\n\tgithub.com/a/b v1.2.3\n\tgithub.com/c/d v0.1.0 // indirect\n)\nrequire github.com/e/f v2.0.0\n"
    assert [(d.name, d.version, d.ecosystem) for d in parse_dependencies("go.mod", go)] == [("github.com/a/b", "v1.2.3", "go"), ("github.com/e/f", "v2.0.0", "go")]
    pkg = '{"dependencies": {"vue": "^3.2"}, "devDependencies": {"vite": "4"}}'
    assert [(d.name, d.version) for d in parse_dependencies("frontend/package.json", pkg)] == [("vue", "^3.2"), ("vite", "4")]
    assert [(d.name, d.version) for d in parse_dependencies("requirements.txt", "requests>=2.0 # c\nnumpy==1.26.0\n-r other.txt\nflask\n")] == [
        ("requests", ">=2.0"), ("numpy", "==1.26.0"), ("flask", None),
    ]
    pyproject = '[project]\ndependencies = ["neo4j>=5.28", "httpx[http2]>=0.27"]\n[tool.poetry.dependencies]\npython = "^3.12"\nrich = {version = "^13"}\n'
    assert [(d.name, d.version) for d in parse_dependencies("pyproject.toml", pyproject)] == [("neo4j", ">=5.28"), ("httpx", ">=0.27"), ("rich", "^13")]
    cargo = '[dependencies]\nserde = "1.0"\ntokio = { version = "1", features = ["full"] }\n'
    assert [(d.name, d.version) for d in parse_dependencies("Cargo.toml", cargo)] == [("serde", "1.0"), ("tokio", "1")]
    pom = "<project><dependencies><dependency><groupId>org.x</groupId><artifactId>lib</artifactId><version>1.2</version></dependency></dependencies></project>"
    assert [(d.name, d.version, d.ecosystem) for d in parse_dependencies("pom.xml", pom)] == [("org.x:lib", "1.2", "maven")]
    assert parse_dependencies("package.json", "{broken") == [] and parse_dependencies("main.go", "x") == []


def test_skip_rules_and_classification():
    assert should_skip("node_modules/a.js") and should_skip("frontend/dist/app.min.js") and should_skip("a/b.pb.go")
    assert should_skip("yarn.lock") and should_skip("x.go", 500_000) and not should_skip("cmd/main.go")
    assert is_noisy_config("i18n/en.json") and is_noisy_config("tests/fixtures/x.yaml") and not is_noisy_config("config.toml")
    assert is_config_path("go.mod") and is_config_path("config.toml.sample") and not is_config_path("main.go")
    assert is_doc_path("README.md") and not is_doc_path("main.go")
    assert languages(["a.go", "b.go", "c.vue", "d.js", "node_modules/x.js"]) == ["go", "vue", "javascript"]


def test_sql_seed_tuples_become_config_values():
    from untangle.ingest.symbols import config_format, parse_config

    sql = """
    INSERT INTO settings (key, value) VALUES
        ('app.root_url', '"http://localhost:9000"'),
        ('app.concurrency', '10'),
        ('privacy.allow_export', 'true'),
        ('privacy.exportable', '["profile", "subscriptions"]'),
        ('smtp', '[{"host": "x"}]'),
        ('app.message', 'it''s fine');
    SELECT * FROM campaigns WHERE status IN ('running', 'paused');
    """
    assert config_format("schema.sql") == "sql_seed"
    values = parse_config("schema.sql", sql)
    assert values == {
        "app.root_url": "http://localhost:9000", "app.concurrency": "10", "privacy.allow_export": "true",
        "privacy.exportable": "profile, subscriptions", "app.message": "it's fine",
    }
    assert parse_config("queries.sql", "SELECT 1 WHERE a IN ('x', 'y');") == {}

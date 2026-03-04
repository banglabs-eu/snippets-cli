"""HTTP client mirroring db.py — talks to the FastAPI backend."""

from pathlib import Path

import httpx

_client: httpx.Client | None = None
_token_path = Path.home() / ".snippets_cli" / "token"


class ConflictError(Exception):
    pass


class AuthExpiredError(Exception):
    pass


def _load_token() -> str | None:
    if _token_path.exists():
        token = _token_path.read_text().strip()
        if token:
            return token
    return None


def save_token(token: str):
    _token_path.parent.mkdir(exist_ok=True)
    _token_path.write_text(token)


def clear_token():
    if _token_path.exists():
        _token_path.unlink()


def logout():
    try:
        _check(_get().post("/logout", headers=_headers()))
    except Exception:
        pass
    clear_token()


def is_authenticated() -> bool:
    return _load_token() is not None


def init(base_url: str):
    global _client
    _client = httpx.Client(base_url=base_url, timeout=30.0)


def health() -> bool:
    r = _get().get("/health", timeout=3.0)
    return r.status_code == 200


def me() -> dict:
    r = _check(_get().get("/me", headers=_headers()))
    return r.json()


def _get() -> httpx.Client:
    if _client is None:
        raise RuntimeError("client not initialized; call client.init(base_url) first")
    return _client


def _headers() -> dict:
    token = _load_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


class BackendError(Exception):
    pass


def _check(response: httpx.Response) -> httpx.Response:
    if response.status_code == 401:
        raise AuthExpiredError(response.json().get("detail", "Unauthorized"))
    if response.status_code == 409:
        raise ConflictError(response.text)
    if response.status_code >= 500:
        raise BackendError(f"Backend error ({response.status_code})")
    response.raise_for_status()
    return response


# --- Auth ---

def register(username: str, password: str) -> dict:
    r = _get().post("/register", json={"username": username, "password": password})
    if r.status_code == 409:
        raise ConflictError("Username already taken")
    if r.status_code == 400:
        raise ValueError(r.json().get("detail", "Bad request"))
    _check(r)
    data = r.json()
    save_token(data["token"])
    return data


def login(username: str, password: str) -> dict:
    r = _get().post("/login", json={"username": username, "password": password})
    if r.status_code == 401:
        raise ValueError("Invalid username or password")
    _check(r)
    data = r.json()
    save_token(data["token"])
    return data


# --- Notes ---

def create_note(body: str, source_id: int | None = None,
                locator_type: str | None = None, locator_value: str | None = None) -> int:
    r = _check(_get().post("/notes", json={
        "body": body,
        "source_id": source_id,
        "locator_type": locator_type,
        "locator_value": locator_value,
    }, headers=_headers()))
    return r.json()["id"]


def update_note_source(note_id: int, source_id: int):
    _check(_get().patch(f"/notes/{note_id}/source", json={"source_id": source_id}, headers=_headers()))


def get_note(note_id: int) -> dict | None:
    r = _get().get(f"/notes/{note_id}", headers=_headers())
    if r.status_code == 404:
        return None
    _check(r)
    return r.json()


def get_all_notes() -> list[dict]:
    r = _check(_get().get("/notes", headers=_headers()))
    return r.json()


def get_notes_by_source(source_id: int) -> list[dict]:
    r = _check(_get().get("/notes", params={"source_id": source_id}, headers=_headers()))
    return r.json()


def get_notes_by_tag(tag_id: int) -> list[dict]:
    r = _check(_get().get("/notes", params={"tag_id": tag_id}, headers=_headers()))
    return r.json()


def get_notes_by_author(author_id: int) -> list[dict]:
    r = _check(_get().get("/notes", params={"author_id": author_id}, headers=_headers()))
    return r.json()


def get_sourceless_notes(note_ids: list[int]) -> list[int]:
    if not note_ids:
        return []
    r = _check(_get().post("/notes/sourceless-check", json={"note_ids": note_ids}, headers=_headers()))
    return r.json()


def bulk_update_note_source(note_ids: list[int], source_id: int):
    if not note_ids:
        return
    _check(_get().post("/notes/bulk-source", json={"note_ids": note_ids, "source_id": source_id}, headers=_headers()))


def delete_note(note_id: int):
    r = _get().delete(f"/notes/{note_id}", headers=_headers())
    if r.status_code == 404:
        return False
    _check(r)
    return True


def get_tags_for_note(note_id: int) -> list[dict]:
    r = _check(_get().get(f"/notes/{note_id}/tags", headers=_headers()))
    return r.json()


def add_tag_to_note(note_id: int, tag_id: int):
    _check(_get().post(f"/notes/{note_id}/tags", json={"tag_id": tag_id}, headers=_headers()))


def remove_tag_from_note(note_id: int, tag_id: int):
    _check(_get().delete(f"/notes/{note_id}/tags/{tag_id}", headers=_headers()))


def get_tags_for_notes(note_ids: list[int]) -> dict[int, list[dict]]:
    if not note_ids:
        return {}
    r = _check(_get().post("/notes/tags/batch", json={"note_ids": note_ids}, headers=_headers()))
    return {int(k): v for k, v in r.json().items()}


# --- Sources ---

def create_source(name: str, source_type_id: int | None = None,
                  year: str | None = None, url: str | None = None,
                  accessed_date: str | None = None, edition: str | None = None,
                  pages: str | None = None, extra_notes: str | None = None,
                  publisher_id: int | None = None) -> int:
    r = _check(_get().post("/sources", json={
        "name": name,
        "source_type_id": source_type_id,
        "year": year,
        "url": url,
        "accessed_date": accessed_date,
        "edition": edition,
        "pages": pages,
        "extra_notes": extra_notes,
        "publisher_id": publisher_id,
    }, headers=_headers()))
    return r.json()["id"]


def get_source(source_id: int) -> dict | None:
    r = _get().get(f"/sources/{source_id}", headers=_headers())
    if r.status_code == 404:
        return None
    _check(r)
    return r.json()


def search_sources(prefix: str, limit: int = 20) -> list[dict]:
    r = _check(_get().get("/sources/search", params={"q": prefix}, headers=_headers()))
    return r.json()


def get_recent_sources(limit: int = 10) -> list[dict]:
    r = _check(_get().get("/sources/recent", headers=_headers()))
    return r.json()


def get_all_sources() -> list[dict]:
    r = _check(_get().get("/sources", headers=_headers()))
    return r.json()


def get_sources_by_author(author_last: str, author_first: str) -> list[dict]:
    r = _check(_get().get("/sources", params={"author_last": author_last, "author_first": author_first}, headers=_headers()))
    return r.json()


def build_citation(source_id: int) -> str:
    r = _check(_get().get(f"/sources/{source_id}/citation", headers=_headers()))
    return r.json()["citation"]


def get_authors_for_source(source_id: int) -> list[dict]:
    r = _check(_get().get(f"/sources/{source_id}/authors", headers=_headers()))
    return r.json()


def add_author(source_id: int, first_name: str, last_name: str, order: int) -> int:
    r = _check(_get().post(f"/sources/{source_id}/authors", json={
        "first_name": first_name,
        "last_name": last_name,
        "order": order,
    }, headers=_headers()))
    return r.json()["id"]


# --- Source Types ---

def get_source_types() -> list[dict]:
    r = _check(_get().get("/source-types", headers=_headers()))
    return r.json()


def get_source_type(type_id: int) -> dict | None:
    r = _get().get(f"/source-types/{type_id}", headers=_headers())
    if r.status_code == 404:
        return None
    _check(r)
    return r.json()


def create_source_type(name: str) -> int:
    r = _check(_get().post("/source-types", json={"name": name}, headers=_headers()))
    return r.json()["id"]


# --- Publishers ---

def search_publishers(prefix: str, limit: int = 20) -> list[dict]:
    r = _check(_get().get("/publishers/search", params={"q": prefix}, headers=_headers()))
    return r.json()


def search_publisher_cities(prefix: str, limit: int = 20) -> list[str]:
    r = _check(_get().get("/publishers/cities", params={"q": prefix}, headers=_headers()))
    return r.json()


def get_or_create_publisher(name: str, city: str | None = None) -> int:
    r = _check(_get().post("/publishers/get-or-create", json={"name": name, "city": city}, headers=_headers()))
    return r.json()["id"]


# --- Authors ---

def get_all_authors() -> list[dict]:
    r = _check(_get().get("/authors", headers=_headers()))
    return r.json()


def get_recent_authors(limit: int = 10) -> list[dict]:
    r = _check(_get().get("/authors/recent", headers=_headers()))
    return r.json()


def search_authors(prefix: str, limit: int = 20) -> list[dict]:
    r = _check(_get().get("/authors/search", params={"q": prefix}, headers=_headers()))
    return r.json()


def search_author_last_names(prefix: str, limit: int = 20) -> list[str]:
    r = _check(_get().get("/authors/last-names", params={"q": prefix}, headers=_headers()))
    return r.json()


def search_author_first_names(prefix: str, limit: int = 20) -> list[str]:
    r = _check(_get().get("/authors/first-names", params={"q": prefix}, headers=_headers()))
    return r.json()


# --- Tags ---

def get_or_create_tag(name: str) -> int:
    r = _check(_get().post("/tags/get-or-create", json={"name": name}, headers=_headers()))
    return r.json()["id"]


def get_tag(tag_id: int) -> dict | None:
    r = _get().get(f"/tags/{tag_id}", headers=_headers())
    if r.status_code == 404:
        return None
    _check(r)
    return r.json()


def get_tag_by_name(name: str) -> dict | None:
    r = _get().get("/tags/by-name", params={"name": name}, headers=_headers())
    if r.status_code == 404:
        return None
    _check(r)
    return r.json()


def search_tags(prefix: str, limit: int = 20) -> list[dict]:
    r = _check(_get().get("/tags/search", params={"q": prefix}, headers=_headers()))
    return r.json()


def get_all_tags() -> list[dict]:
    r = _check(_get().get("/tags", headers=_headers()))
    return r.json()


def get_recent_tags(limit: int = 10) -> list[dict]:
    r = _check(_get().get("/tags/recent", headers=_headers()))
    return r.json()

"""Recovery entry point for interrupted library writes."""

from .arrangements import LibraryStore


def recover_pending_writes(store: LibraryStore) -> dict:
    return store.recover_pending_writes()

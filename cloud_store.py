from __future__ import annotations
from typing import Any, Dict, Tuple
from storage import empty_workspace, normalize_workspace


def create_supabase_client(url: str, key: str):
    from supabase import create_client
    return create_client(url, key)


def sign_in(client, email: str, password: str) -> Tuple[Any, Any]:
    res = client.auth.sign_in_with_password({"email": email, "password": password})
    return res.user, res.session


def sign_up(client, email: str, password: str) -> Tuple[Any, Any]:
    res = client.auth.sign_up({"email": email, "password": password})
    return res.user, res.session


def sign_out(client) -> None:
    client.auth.sign_out()


def load_cloud_workspace(client, user_id: str) -> Dict[str, Any]:
    res = client.table("teacher_workspaces").select("workspace").eq("user_id", user_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        data = empty_workspace()
        save_cloud_workspace(client, user_id, data)
        return data
    return normalize_workspace(rows[0].get("workspace"))


def save_cloud_workspace(client, user_id: str, data: Dict[str, Any]) -> None:
    payload = {"user_id": user_id, "workspace": normalize_workspace(data)}
    client.table("teacher_workspaces").upsert(payload, on_conflict="user_id").execute()

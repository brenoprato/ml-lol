"""Unit tests for resilient HTTP client using respx mocks."""

import pytest
import respx
import httpx
from src.core.exceptions import AuthenticationException, ResourceNotFoundException
from src.core.http_client import ResilientHTTPClient


@respx.mock
def test_http_client_get_200() -> None:
    respx.get("https://br1.api.riotgames.com/test").respond(
        status_code=200,
        json={"status": "ok"},
        headers={"X-App-Rate-Limit-Count": "1:1,1:120"},
    )

    with ResilientHTTPClient(api_key="RGAPI-test") as client:
        response = client.get("https://br1.api.riotgames.com/test")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@respx.mock
def test_http_client_auth_failure() -> None:
    respx.get("https://br1.api.riotgames.com/test").respond(
        status_code=401,
        json={"status": {"message": "Unauthorized"}},
    )

    with ResilientHTTPClient(api_key="RGAPI-test") as client:
        with pytest.raises(AuthenticationException):
            client.get("https://br1.api.riotgames.com/test")


@respx.mock
def test_http_client_404_not_found() -> None:
    respx.get("https://br1.api.riotgames.com/test").respond(
        status_code=404,
        json={"status": {"message": "Not Found"}},
    )

    with ResilientHTTPClient(api_key="RGAPI-test") as client:
        with pytest.raises(ResourceNotFoundException):
            client.get("https://br1.api.riotgames.com/test")


@respx.mock
def test_http_client_retry_on_429() -> None:
    # First response 429, second 200
    route = respx.get("https://br1.api.riotgames.com/test")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0.1"}),
        httpx.Response(200, json={"result": "success"}),
    ]

    with ResilientHTTPClient(api_key="RGAPI-test") as client:
        response = client.get("https://br1.api.riotgames.com/test")
        assert response.status_code == 200
        assert response.json() == {"result": "success"}
        assert route.call_count == 2

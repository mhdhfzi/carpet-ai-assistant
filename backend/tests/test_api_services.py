from typing import Any

from fastapi.testclient import TestClient

SHAMPOO = {
    "name": "Carpet shampoo",
    "description": "Deep shampoo for wall-to-wall carpet",
    "pricing_unit": "per_sqft",
    "unit_price": "1.20",
    "minimum_charge": "80.00",
}


def create_service(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post("/api/services", json={**SHAMPOO, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_get_service(client: TestClient) -> None:
    created = create_service(client)

    response = client.get(f"/api/services/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Carpet shampoo"
    assert body["unit_price"] == "1.20"  # money is a string, so no float rounding
    assert body["is_active"] is True


def test_duplicate_service_name_is_rejected(client: TestClient) -> None:
    create_service(client)

    response = client.post("/api/services", json=SHAMPOO)

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_negative_price_is_rejected(client: TestClient) -> None:
    response = client.post("/api/services", json={**SHAMPOO, "unit_price": "-1"})

    assert response.status_code == 422


def test_update_service_changes_only_given_fields(client: TestClient) -> None:
    created = create_service(client)

    response = client.patch(f"/api/services/{created['id']}", json={"unit_price": "1.50"})

    assert response.status_code == 200
    assert response.json()["unit_price"] == "1.50"
    assert response.json()["minimum_charge"] == "80.00"


def test_delete_deactivates_and_hides_service_from_default_list(client: TestClient) -> None:
    created = create_service(client)

    assert client.delete(f"/api/services/{created['id']}").status_code == 204

    assert client.get("/api/services").json() == []
    all_services = client.get("/api/services", params={"include_inactive": True}).json()
    assert [s["is_active"] for s in all_services] == [False]


def test_missing_service_returns_404(client: TestClient) -> None:
    assert client.get("/api/services/999999").status_code == 404
    assert client.patch("/api/services/999999", json={"name": "x"}).status_code == 404


def test_service_with_price_range(client: TestClient) -> None:
    created = create_service(
        client, name="Karpet Handmade", unit_price="2.50", unit_price_max="4.00"
    )

    assert (created["unit_price"], created["unit_price_max"]) == ("2.50", "4.00")


def test_fixed_price_service_has_no_max(client: TestClient) -> None:
    assert create_service(client)["unit_price_max"] is None


def test_inverted_price_range_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/services", json={**SHAMPOO, "unit_price": "4.00", "unit_price_max": "2.50"}
    )

    assert response.status_code == 422
    assert "unit_price_max" in response.json()["detail"]


def test_patch_cannot_invert_existing_range(client: TestClient) -> None:
    created = create_service(client, unit_price="2.50", unit_price_max="4.00")

    response = client.patch(f"/api/services/{created['id']}", json={"unit_price": "5.00"})

    assert response.status_code == 422


def test_patch_can_clear_range_back_to_fixed_price(client: TestClient) -> None:
    created = create_service(client, unit_price="2.50", unit_price_max="4.00")

    response = client.patch(f"/api/services/{created['id']}", json={"unit_price_max": None})

    assert response.status_code == 200
    assert response.json()["unit_price_max"] is None


def test_patch_rejects_null_for_required_fields(client: TestClient) -> None:
    created = create_service(client)

    response = client.patch(f"/api/services/{created['id']}", json={"name": None})

    assert response.status_code == 422
    assert "cannot be null: name" in response.text

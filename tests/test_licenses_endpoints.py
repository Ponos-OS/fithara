from httpx import AsyncClient


async def test_list_licenses_returns_only_active_ordered_without_body(client: AsyncClient) -> None:
    response = await client.get("/v1/licenses")  # act

    assert response.status_code == 200
    body = response.json()
    assert [license_["id"] for license_ in body["licenses"]] == ["FIXTURE-ACTIVE"]
    assert "body" not in body["licenses"][0]


async def test_get_license_returns_verbatim_body_for_active_id(client: AsyncClient) -> None:
    response = await client.get("/v1/licenses/FIXTURE-ACTIVE")  # act

    assert response.status_code == 200
    assert (
        response.json()["body"]
        == "# Fixture Active License\n\nFixture license body for FIXTURE-ACTIVE."
    )


async def test_get_license_returns_404_for_unknown_id(client: AsyncClient) -> None:
    response = await client.get("/v1/licenses/DOES-NOT-EXIST")  # act

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "UNKNOWN_LICENSE"


async def test_get_license_returns_410_for_inactive_id(client: AsyncClient) -> None:
    response = await client.get("/v1/licenses/FIXTURE-INACTIVE")  # act

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "LICENSE_INACTIVE"

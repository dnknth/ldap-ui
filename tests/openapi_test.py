import json
import unittest
from http import HTTPStatus
from pathlib import Path

from fastapi.testclient import TestClient
from ldap_ui.app import app

JSON = Path(__file__).parent / "resources" / "openapi.json"


class OpenApiTestTest(unittest.TestCase):
    def test_openapi_json(self):
        with TestClient(app) as client:
            result = client.get("/openapi.json")
            self.assertEqual(result.status_code, HTTPStatus.OK)

            actual_api = result.json()

        with JSON.with_stem(JSON.stem + "-actual").open("w") as actual_json:
            json.dump(actual_api, actual_json, indent=2, sort_keys=True)

        if not JSON.exists():
            with JSON.open("w") as expected_json:
                json.dump(actual_api, expected_json, indent=2, sort_keys=True)
        else:
            with JSON.open("r") as expected_json:
                self.assertDictEqual(
                    json.load(expected_json),
                    actual_api,
                    "OpenAPI changed, please commit it",
                )

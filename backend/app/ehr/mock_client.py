"""Integration layer: vendor logic lives here, never in AI layer."""
import httpx, os
class EHRClient:
    def __init__(self, base_url: str = "", api_key: str = ""):
        self.base = (base_url or os.getenv("MOCK_EHR_URL", "http://mock-ehr:8001")).rstrip("/")
        self.key = api_key or os.getenv("MOCK_EHR_API_KEY", "mock-ehr-dev-key")
    def _h(self): return {"X-API-Key": self.key, "Content-Type": "application/json"}
    def _url(self, p): return f"{self.base}{p}"
    async def create_appointment(self, payload: dict, idempotency_key: str = ""):
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.post(self._url("/ehr/appointments"), json=payload, headers={**self._h(), "Idempotency-Key": idempotency_key})
            r.raise_for_status(); return r.json()
    async def get_appointment(self, ext_id: str):
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(self._url(f"/ehr/appointments/{ext_id}"), headers=self._h())
            if r.status_code == 404: return None
            r.raise_for_status(); return r.json()
    async def update_appointment(self, ext_id: str, patch: dict):
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.patch(self._url(f"/ehr/appointments/{ext_id}"), json=patch, headers=self._h())
            r.raise_for_status(); return r.json()
    async def cancel_appointment(self, ext_id: str):
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.delete(self._url(f"/ehr/appointments/{ext_id}"), headers=self._h())
            r.raise_for_status(); return r.json()
    async def lookup_patient(self, q: str):
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(self._url("/ehr/patients"), params={"q": q}, headers=self._h())
            r.raise_for_status(); return r.json()
    async def lookup_provider(self, q: str = ""):
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(self._url("/ehr/providers"), params={"q": q}, headers=self._h())
            r.raise_for_status(); return r.json()
    async def health(self):
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(self._url("/health"))
            return r.json() if r.status_code == 200 else {"ok": False}

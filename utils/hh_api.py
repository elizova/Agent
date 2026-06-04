import time

import requests

HEADERS = {"HH-User-Agent": "MySuperApp/1.0 (elizova.v@gmail.com)"}
BASE_URL = "https://api.hh.ru"

_areas_cache = None


def _load_areas():
    global _areas_cache
    if _areas_cache is None:
        resp = requests.get(f"{BASE_URL}/areas", headers=HEADERS)
        _areas_cache = resp.json() if resp.status_code == 200 else []
    return _areas_cache


def get_area_id(area_name: str):
    areas = _load_areas()

    def search(areas_list, name):
        for area in areas_list:
            if name.lower() in area["name"].lower():
                return area["id"]
            if "areas" in area:
                found = search(area["areas"], name)
                if found:
                    return found
        return None

    return search(areas, area_name)


def safe_request(url, params=None, access_token=None, retries=3):
    headers = HEADERS.copy()
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    for attempt in range(retries):
        try:
            response = requests.get(
                url, headers=headers, params=params, timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except requests.exceptions.ConnectionError:
            time.sleep(1)
    return None


def search_vacancies(
    params_dict, access_token=None, page: int = 0, per_page: int = 20
):
    params = {
        k: v
        for k, v in dict(params_dict).items()
        if v is not None and str(v).lower() not in ("null", "none", "")
    }
    params["page"] = page
    params["per_page"] = min(per_page, 50)

    if "area" in params:
        area = params["area"]
        if isinstance(area, str) and not area.isdigit():
            area_id = get_area_id(area)
            if area_id:
                params["area"] = area_id
            else:
                del params["area"]

    url = f"{BASE_URL}/vacancies"
    return safe_request(url, params, access_token=access_token)


def get_vacancy_details(vacancy_id, access_token=None):
    url = f"{BASE_URL}/vacancies/{vacancy_id}"
    return safe_request(url, access_token=access_token)


def format_salary(
    vac: dict | None = None, details: dict | None = None
) -> str | None:
    sal = None
    if vac:
        sal = vac.get("salary")
    if not sal and details:
        sal = details.get("salary")
    if not sal:
        return None

    cur = sal.get("currency") or ""
    cur_labels = {"RUR": "руб.", "USD": "$", "EUR": "€", "KZT": "тг."}
    cur_s = cur_labels.get(cur, cur)

    g_from = sal.get("from")
    g_to = sal.get("to")
    if g_from and g_to:
        return f"{g_from:,} – {g_to:,} {cur_s}".replace(",", " ")
    if g_from:
        return f"от {g_from:,} {cur_s}".replace(",", " ")
    if g_to:
        return f"до {g_to:,} {cur_s}".replace(",", " ")
    return None

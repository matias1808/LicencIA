from licencia.metric_seed import baseline_samples


def test_baseline_has_exactly_178_rows():
    rows = baseline_samples()
    assert len(rows) == 178


def test_baseline_uses_only_empresas_domain():
    rows = baseline_samples()
    for message, _ in rows:
        if "@" in message:
            assert "@empresas.com.pe" in message


def test_baseline_contains_four_boundary_cases():
    rows = dict(baseline_samples())
    assert rows["Qué licencias disponibles tiene juan.perez@empresas.com.pe"] == "user_licenses"
    assert rows["Qué usuarios tienen Power BI para transferirla"] == "reassign"
    assert rows["Qué licencias hay disponibles"] == "catalog"
    assert rows["Qué usuarios tienen Power BI para retirarla"] == "unassign"

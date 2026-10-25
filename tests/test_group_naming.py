from licencia.security_groups import group_name_for_license


def test_security_group_nomenclature():
    assert group_name_for_license("M365 E3") == "GRP_LICENCIAMS_M365_E3_USERS"
    assert group_name_for_license("Power BI Premium USL") == "GRP_LICENCIAMS_POWER_BI_PREMIUM_USL_USERS"
    assert group_name_for_license("Planner & Project P3") == "GRP_LICENCIAMS_PLANNER_PROJECT_P3_USERS"
    assert group_name_for_license("W365 Ent 4vCPU/16GB/128GB") == "GRP_LICENCIAMS_W365_ENT_4VCPU_16GB_128GB_USERS"

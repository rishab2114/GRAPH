"""Atom catalogue for E01: constraint types of the RCPSP-extension literature that the exact solver supports.

`mapping_status` stays "unverified" until a person checks the definition against the cited source's text (Codex L03:
start from manually verified mappings, not labels with author counts). `query` is the OpenAlex phrase used later for
literature counts (coherence and availability), always combined with the RCPSP anchor.
"""
SURVEY_2010 = "10.1016/j.ejor.2009.11.005"      # Hartmann & Briskorn, survey of RCPSP variants and extensions
SURVEY_2022 = "10.1016/j.ejor.2021.05.004"      # updated survey
PSPLIB = "10.1016/s0377-2217(96)00170-1"        # Kolisch & Sprecher, project scheduling problem library

ATOMS = {
    "precedence": {"definition": "finish-to-start precedence: an activity starts only after each predecessor finishes",
                   "solver": "precedence", "query": "precedence", "source_doi": SURVEY_2010, "mapping_status": "unverified"},
    "renewable_capacity": {"definition": "a renewable resource with constant per-period capacity shared by running activities",
                           "solver": "resource.capacity", "query": "renewable resource", "source_doi": PSPLIB,
                           "mapping_status": "unverified"},
    "release_dates": {"definition": "an activity cannot start before its release (ready) time",
                      "solver": "tasks.release", "query": "release dates", "source_doi": SURVEY_2010, "mapping_status": "unverified"},
    "deadlines": {"definition": "an activity must finish by its deadline (due date as a hard constraint)",
                  "solver": "tasks.deadline", "query": "deadlines", "source_doi": SURVEY_2010, "mapping_status": "unverified"},
    "resource_calendar": {"definition": "resource capacity varies over time (reduced availability in given intervals)",
                          "solver": "resource.calendar", "query": "resource calendars", "source_doi": SURVEY_2022,
                          "mapping_status": "unverified"},
    "min_time_lags": {"definition": "generalised precedence: an activity starts at least a given lag after another starts",
                      "solver": "lags", "query": "minimum time lags", "source_doi": SURVEY_2010, "mapping_status": "unverified"},
}
BASE = ("precedence", "renewable_capacity")      # every composition contains the RCPSP core

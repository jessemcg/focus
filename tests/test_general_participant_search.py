"""General role/representation metadata remains a hearing-scoped search lead."""
from focus.agent_helper import _participant_aliases_for_page
from test_profile_artifacts import general_participant


def test_general_role_and_represented_client_are_search_leads_not_cross_hearing_aliases():
    index = general_participant()
    index["hearings"][0]["counsel"][0]["represents"] = "Synthetic Intervenor"
    source_map = {"participant_index": index}
    aliases = _participant_aliases_for_page(source_map, 2)
    assert "Synthetic Intervenor" in aliases
    assert "Counsel for claimant" in aliases
    assert "Court-appointed technical adviser" in aliases
    assert _participant_aliases_for_page(source_map, 4) == []

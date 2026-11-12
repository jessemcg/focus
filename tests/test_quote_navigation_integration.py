"""Fictional schema-3 and real GTK-handler controls, not native input claims."""
import copy
import hashlib
import json
from types import SimpleNamespace as NS

import pytest
from gi.repository import Gtk, Gdk

from focus.app import Focus
from focus.quote_navigation import load_summary_navigation, navigation_display, normalize_source_display
from focus.quote_projection import project_summary, page_fragments
from focus.summary_editions import load_summary_edition, render_page_display, SummaryEditionError
from focus.profile_artifacts import quotation_navigation_hash
from test_quote_navigation import bundle, FIXTURE


def edition3(tmp_path):
    root,path,meta = bundle(tmp_path)
    text = path.read_bytes().decode()
    clean,_mapping,spans = project_summary(text,meta)
    split = spans[0]['start'] + 8
    page_texts = {1:clean[:split],2:clean[split:]}
    fragments = page_fragments(text,meta,page_texts)
    directory = root/'summaries/editions';directory.mkdir()
    pdf = directory/(path.stem+'.pdf');pdf.write_bytes(b'Fictional PDF fixture, not rendered acceptance')
    pages = directory/(path.stem+'.pages.json')
    payload = {'artifact':'recordprep-summary-pages','schema_version':3,'kind':'hearings',
        'layout':{'id':'recordprep-summary-letter-v3'},
        'source':{'path':path.relative_to(root).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                  'navigation_sha256':meta['navigation_sha256']},
        'pdf':{'path':pdf.relative_to(root).as_posix(),'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'page_count':2},
        'pages':[{'page':n,'text':value,'source_first_line':1,'source_last_line':1,'links':[],
                  'quotes':fragments[n]} for n,value in page_texts.items()]}
    pages.write_text(json.dumps(payload))
    return root,path,meta,pages,payload


def load_edition(root,path):
    return load_summary_edition(focus_source='hearing',summary_path=path,bundle_root=root)


def test_schema3_fragments_share_exact_occurrence_not_shorter_phrase_search(tmp_path):
    root,path,meta,_pages,_payload = edition3(tmp_path)
    edition = load_edition(root,path)
    assert edition.schema_version == 3
    assert edition.navigation_sha256 == meta['navigation_sha256']
    first = render_page_display(edition,1)
    second = render_page_display(edition,2)
    assert first.quote_occurrences[0][2] == second.quote_occurrences[0][2] == meta['quote_occurrences'][0]['occurrence_id']
    assert first.phrase_spans[0][2] == second.phrase_spans[0][2] == meta['quote_occurrences'][0]['display_text']


@pytest.mark.parametrize('damage',['id','missing_id','label','metadata_missing','navigation_only','omitted_fragment','downgrade'])
def test_schema3_damage_never_becomes_a_legacy_edition(tmp_path,damage):
    root,path,meta,pages,payload = edition3(tmp_path)
    if damage == 'metadata_missing':
        path.with_suffix('.meta.json').unlink()
    elif damage == 'navigation_only':
        meta['quote_occurrences'][0]['initial_case']='preserve'
        meta['navigation_sha256']=quotation_navigation_hash(meta)
        path.with_suffix('.meta.json').write_text(json.dumps(meta))
    elif damage == 'downgrade':
        payload['schema_version']=2
        payload['source'].pop('navigation_sha256')
        for page in payload['pages']:
            for quote in page['quotes']:quote.pop('occurrence_id')
        pages.write_text(json.dumps(payload))
    else:
        q = payload['pages'][0]['quotes'][0]
        if damage == 'id': q['occurrence_id']='wrong identity'
        if damage == 'missing_id': del q['occurrence_id']
        if damage == 'label': q['label']='wrong label'
        if damage == 'omitted_fragment': payload['pages'][0]['quotes']=[]
        pages.write_text(json.dumps(payload))
    with pytest.raises(SummaryEditionError):
        load_edition(root,path)


def test_continuous_ledger_only_display_maps_raw_offsets(tmp_path):
    root,path,meta = bundle(tmp_path)
    nav = load_summary_navigation(summary_path=path,bundle_root=root,permitted_pages=[12])
    text = path.read_bytes().decode()
    display,spans = navigation_display(text,nav)
    for a,b,identity in spans:
        occurrence = nav.occurrence(identity)
        assert display[a:b] == occurrence.display_text
    assert '“' not in display and '”' not in display
    with pytest.raises(ValueError):
        navigation_display(text+' changed',nav)


def gtk_harness(root,path):
    nav = load_summary_navigation(summary_path=path,bundle_root=root,permitted_pages=[12])
    buffer = Gtk.TextBuffer()
    color=Gdk.RGBA();color.parse('#334455')
    harness = NS(input_dir=root,pages=[12],_summary_loaded_path=path,_summary_navigation_path=path,
                 _summary_navigation=nav,_summary_buffer=buffer,_summary_view=None,_summary_link_tags=[],
                 _summary_link_tag_lookup={},_resolve_ai_quote_color=lambda view:color,
                 _reading_pages=set(),_reading_snapshot=(12,'fictional'),toasts=[],calls=[])
    harness._quotation_navigation_for_current=lambda:Focus._quotation_navigation_for_current(harness)
    harness._ai_transient_toast=harness.toasts.append
    harness._apply_grep=lambda value:pytest.fail('New navigation must not invoke record-wide phrase search')
    harness._activate_quotation=lambda identity:Focus._activate_quotation(harness,identity)
    harness._load_quotation_navigation=lambda p:Focus._load_quotation_navigation(harness,p)
    harness._show_page_from_link=lambda page:harness.calls.append(('page',page))
    source=normalize_source_display(FIXTURE['source'])[0]
    harness._read_page_text=lambda page:(source,'',[])
    harness._render_page_display=lambda page,text,highlights:(text,highlights)
    harness._set_text=lambda text,highlights,literal=False:harness.calls.append(('display',text,highlights,literal))
    harness._map_markdown_offset=lambda a,m:Focus._map_markdown_offset(harness,a,m)
    harness._scroll_current_record_offset=lambda *args:False
    return harness


def test_real_gtk_tags_disable_unresolved_and_handler_highlights_exact_later_span(tmp_path):
    root,path,meta = bundle(tmp_path)
    harness=gtk_harness(root,path)
    Focus._apply_anchored_summary(harness,path.read_bytes().decode(),harness._summary_navigation)
    lookup=list(harness._summary_link_tag_lookup.values())
    assert lookup == [('quotation',meta['quote_occurrences'][0]['occurrence_id'])]
    Focus._activate_link(harness,lookup[0])
    assert harness.calls[0] == ('page','12')
    _kind,text,highlights,_literal=harness.calls[1]
    a,b=highlights[0]
    assert text[a:b] == 'notice before entry'
    assert a > text.lower().index('notice before entry')
    assert not harness.toasts


def test_stale_click_does_not_navigate_or_search_and_warns(tmp_path):
    root,path,meta = bundle(tmp_path)
    harness=gtk_harness(root,path)
    (root/'text_pages/0012.txt').write_text('Fictional source changed')
    Focus._activate_link(harness,('quotation',meta['quote_occurrences'][0]['occurrence_id']))
    assert not harness.calls
    assert harness.toasts and harness._summary_navigation.unresolved_count == 2

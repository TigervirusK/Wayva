"""AI place decisions are mocked; scheduling, constraints and arithmetic are real."""
import asyncio
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
import json

from fastapi import HTTPException
import pytest

from app.config import Settings
from app.schemas.trips import ItineraryInput
from app.services.compact_planning import PlaceSelection, materialize
from app.services import ollama_ai
from app.services.travel_quality import constraints_for, reference_context, validate_quality


@pytest.fixture
def context():
    return {'destination': 'Tokyo, Japan', 'start_date': '2027-05-01', 'end_date': '2027-05-01', 'budget': '3000.00', 'travelers': 2, 'currency': 'USD', 'itinerary': [],
        'planning_constraints': constraints_for('Plan just the first day between 09:00 and 21:00. Stay within Tokyo.'),
        'place_references': reference_context('Tokyo')}


@pytest.fixture
def selected():
    return {'days': [{'date': '2027-05-01', 'sights': ['sensoji', 'akihabara'], 'lunch': 'asakusa-mugitoro', 'dinner': 'shibuya-yokocho'}]}


def trip(context):
    return SimpleNamespace(destination=context['destination'], start_date=date.fromisoformat(context['start_date']), end_date=date.fromisoformat(context['end_date']),
        budget=Decimal(context['budget']), travelers=context['travelers'], itinerary=[ItineraryInput(**item) for item in context['itinerary']])


def test_selected_places_get_valid_slots_buffers_and_explainable_group_envelopes(context, selected):
    generated = materialize(PlaceSelection.model_validate(selected), trip(context), context['planning_constraints'])
    items = [ItineraryInput(**item.model_dump(), status='planned') for item in generated.activities]
    places, warnings = validate_quality(items, trip(context), context['planning_constraints'])
    assert len(items) == 4
    assert all('09:00' <= item.start_time.strftime('%H:%M') < item.end_time.strftime('%H:%M') <= '21:00' for item in items)
    assert all(place['city'] == 'Tokyo' for place in places)
    assert sum((item.estimated_cost for item in items), Decimal(0)) == Decimal('900.00')
    assert any('10%' in note and '20%' in note for note in generated.notes)
    assert context['itinerary'] == []


@pytest.mark.parametrize('mutation', ['unknown_id', 'wrong_category', 'outside_date', 'duplicate_date', 'too_narrow'])
def test_selection_cannot_bypass_supported_ids_dates_or_available_slots(context, selected, mutation):
    if mutation == 'unknown_id': selected['days'][0]['sights'] = ['not-a-real-catalog-id']
    elif mutation == 'wrong_category': selected['days'][0]['lunch'] = 'sensoji'
    elif mutation == 'outside_date': selected['days'][0]['date'] = '2027-05-07'
    elif mutation == 'duplicate_date': selected['days'] *= 2
    else: context['planning_constraints'].update(start_time='09:00', end_time='10:00')
    with pytest.raises(HTTPException) as failure:
        materialize(PlaceSelection.model_validate(selected), trip(context), context['planning_constraints'])
    assert failure.value.status_code == 422


def test_saved_place_is_counted_without_reinserting_or_rescheduling_it(context, selected):
    context['itinerary'] = [{'date':'2027-05-01','start_time':'09:00','end_time':'10:30','title':'Sensoji Temple','description':'Fixed saved visit',
        'location':'Asakusa, Tokyo','estimated_cost':'50.00','item_type':'activity','status':'planned'}]
    generated = materialize(PlaceSelection.model_validate(selected), trip(context), context['planning_constraints'])
    assert len(generated.activities) == 3
    assert all('Sensoji' not in item.title for item in generated.activities)
    assert context['itinerary'][0]['start_time'] == '09:00'


def test_semantic_planning_decision_requires_a_real_selection_not_an_empty_promise(context, selected, monkeypatch):
    request = AsyncMock(side_effect=[{'content':json.dumps({'intent':'plan'})},
        {'content':json.dumps({'reply':'Places to review.','plan':None,'requirements':None,'selection':selected})}])
    monkeypatch.setattr(ollama_ai, '_request', request)
    turn = asyncio.run(ollama_ai.local_converse([{'role':'user','content':'A relaxed schedule please; save only after I approve.'}], None,
        Settings(_env_file=None, ai_mode='ollama', openai_api_key=None), context))
    assert turn.plan is not None and len(turn.plan.activities) == 4
    assert request.await_count == 2
    schema = request.await_args.kwargs['schema']
    assert schema['properties']['ranking']['type'] == 'object'
    assert schema['properties']['plan'] == {'type':'null'}
    assert 'sensoji' in schema['properties']['ranking']['properties']['sight_scores']['properties']


def test_plan_intent_cannot_return_review_words_without_a_reviewable_draft(context, monkeypatch):
    request = AsyncMock(side_effect=[{'content':'{"intent":"plan"}'}, {'content':'{"reply":"Review this prepared itinerary.","plan":null,"requirements":null,"selection":null}'}])
    monkeypatch.setattr(ollama_ai, '_request', request)
    with pytest.raises(HTTPException) as failure:
        asyncio.run(ollama_ai.local_converse([{'role':'user','content':'Make my plan'}],None,Settings(_env_file=None,ai_mode='ollama'),context))
    assert failure.value.status_code == 502


def test_explanation_is_a_normal_answer_without_a_selection(context, monkeypatch):
    request = AsyncMock(side_effect=[{'content':'{"intent":"answer"}'}, {'content':'{"reply":"It leaves room to rest.","plan":null,"requirements":null,"selection":null}'}])
    monkeypatch.setattr(ollama_ai, '_request', request)
    turn = asyncio.run(ollama_ai.local_converse([{'role':'user','content':'Why that place?'}],None,Settings(_env_file=None,ai_mode='ollama'),context))
    assert turn.plan is None and turn.reply == 'It leaves room to rest.'


def test_duplicate_sights_are_rejected_with_unused_choices_instead_of_faking_new_attractions(context, selected):
    selected['days'][0]['sights'] = ['sensoji', 'sensoji']
    with pytest.raises(HTTPException) as failure:
        materialize(PlaceSelection.model_validate(selected), trip(context), context['planning_constraints'])
    assert 'repeat' in failure.value.detail and 'Unused reference choices' in failure.value.detail


def test_ranked_candidates_count_fixed_sights_and_keep_all_new_sights_distinct(context):
    from app.services.compact_planning import RankedSelection, ranked_selection
    context['itinerary'] = [{'id':'owned-item','trip_id':'owned-trip','date':'2027-05-01','start_time':'09:00','end_time':'10:30',
        'title':'Sensoji Temple','location':'Asakusa, Tokyo','estimated_cost':'10.00','item_type':'activity','status':'planned'}]
    ranking = RankedSelection(dates=['2027-05-01'], sight_scores={'sensoji':5,'akihabara':4}, lunch_scores={}, dinner_scores={},
        sights_per_day=2, include_lunch=False, include_dinner=False, spending_style='standard')
    chosen = ranked_selection(ranking, context)
    assert chosen.days[0].sights == ['akihabara']


def test_partial_ranked_revision_preserves_other_days_and_reduces_only_its_allowances(context, selected, monkeypatch):
    context['end_date'] = '2027-05-02'
    selected['days'].append({'date':'2027-05-02','sights':['ueno-park','tokyo-national-museum'],'lunch':'ameyoko','dinner':'tokyo-ramen-street'})
    old = materialize(PlaceSelection.model_validate(selected), trip(context), context['planning_constraints'])
    data = {'dates':['2027-05-01'],'sight_scores':{p['id']:3 for p in context['place_references']['places'] if p['kind']=='activity'},
        'lunch_scores':{p['id']:3 for p in context['place_references']['places'] if p['kind']=='food'},
        'dinner_scores':{p['id']:3 for p in context['place_references']['places'] if p['kind']=='food'},
        'sights_per_day':2,'include_lunch':True,'include_dinner':True,'spending_style':'economy'}
    context['planning_constraints'] = constraints_for('Make just the first day cheaper.',previous=context['planning_constraints'])
    response = {'reply':'A revision to review.','plan':None,'requirements':None,'selection':None,'ranking':data}
    monkeypatch.setattr(ollama_ai, '_request', AsyncMock(side_effect=[{'content':'{"intent":"plan"}'},{'content':json.dumps(response)}]))
    result = asyncio.run(ollama_ai.local_converse([{'role':'user','content':'Make just the first day cheaper.'}],None,
        Settings(_env_file=None,ai_mode='ollama'),context,{'plan':old.model_dump()}))
    assert [i.model_dump() for i in result.plan.activities if i.date=='2027-05-02'] == [i.model_dump() for i in old.activities if i.date=='2027-05-02']
    assert sum(Decimal(i.estimated_cost) for i in result.plan.activities) < sum(Decimal(i.estimated_cost) for i in old.activities)

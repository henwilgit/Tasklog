from datetime import date

import pytest

from app import next_occurrence, parse_date, fmt_date


# ---- Pure helper functions ----

def test_parse_date():
    assert parse_date('20260315') == date(2026, 3, 15)


def test_fmt_date():
    assert fmt_date(date(2026, 3, 15)) == '20260315'


@pytest.mark.parametrize('rule, from_date, expected', [
    ('daily', '20260101', '20260102'),
    ('weekly', '20260101', '20260108'),
    ('monthly', '20260131', '20260228'),   # clamps to Feb's last day
    ('quarterly', '20260131', '20260430'),  # clamps to Apr's last day
    ('annually', '20240229', '20250228'),  # leap day clamps to Feb 28
    ('lastday:TUE', '20260101', '20260224'),
    ('firstday:FRI', '20260101', '20260206'),
])
def test_next_occurrence(rule, from_date, expected):
    assert next_occurrence(rule, from_date) == expected


def test_next_occurrence_unknown_rule_returns_none():
    assert next_occurrence('bogus', '20260101') is None


# ---- Routes ----

def test_index_serves_html(client):
    resp = client.get('/')
    assert resp.status_code == 200


def test_create_and_get_entry_by_date(client):
    resp = client.post('/api/entries', json={
        'date': '20260315', 'type': 'todo', 'text': 'Buy milk'
    })
    assert resp.status_code == 201
    body = resp.get_json()
    assert body['text'] == 'Buy milk'
    assert body['type'] == 'todo'
    assert body['priority'] == 1
    assert body['date'] == '20260315'

    resp = client.get('/api/entries?date=20260315')
    assert resp.status_code == 200
    entries = resp.get_json()
    assert len(entries) == 1
    assert entries[0]['text'] == 'Buy milk'


def test_priority_increments_per_date_and_type(client):
    for text in ['First', 'Second', 'Third']:
        client.post('/api/entries', json={'date': '20260315', 'type': 'todo', 'text': text})

    entries = client.get('/api/entries?date=20260315').get_json()
    assert [e['priority'] for e in entries] == [1, 2, 3]
    assert [e['text'] for e in entries] == ['First', 'Second', 'Third']


def test_get_entries_requires_date_or_range(client):
    resp = client.get('/api/entries')
    assert resp.status_code == 400


def test_get_entries_date_range_with_type_filter(client):
    client.post('/api/entries', json={'date': '20260301', 'type': 'todo', 'text': 'A'})
    client.post('/api/entries', json={'date': '20260302', 'type': 'done', 'text': 'B'})
    client.post('/api/entries', json={'date': '20260310', 'type': 'todo', 'text': 'C'})

    entries = client.get('/api/entries?from=20260301&to=20260305').get_json()
    assert len(entries) == 2

    entries = client.get('/api/entries?from=20260301&to=20260305&type=done').get_json()
    assert len(entries) == 1
    assert entries[0]['text'] == 'B'


def test_update_entry(client):
    created = client.post('/api/entries', json={
        'date': '20260315', 'type': 'todo', 'text': 'Original'
    }).get_json()

    resp = client.put(f'/api/entries/{created["id"]}', json={
        'date': '20260315', 'type': 'todo', 'text': 'Updated'
    })
    assert resp.status_code == 200
    assert resp.get_json()['text'] == 'Updated'


def test_update_entry_not_found(client):
    resp = client.put('/api/entries/999', json={
        'date': '20260315', 'type': 'todo', 'text': 'x'
    })
    assert resp.status_code == 404


def test_promote_todo_to_done(client):
    created = client.post('/api/entries', json={
        'date': '20260315', 'type': 'todo', 'text': 'Task'
    }).get_json()

    resp = client.put(f'/api/entries/{created["id"]}', json={
        'date': '20260315', 'type': 'done', 'text': 'Task'
    })
    body = resp.get_json()
    assert resp.status_code == 200
    assert body['type'] == 'done'
    assert 'next_entry' not in body


def test_promote_recurring_todo_creates_next_occurrence(client):
    entry = client.post('/api/entries', json={
        'date': '20260315', 'type': 'todo', 'text': 'Daily task', 'recur_rule': 'daily'
    }).get_json()
    assert entry['recur_id']  # auto-generated for new recurring series

    body = client.put(f'/api/entries/{entry["id"]}', json={
        'date': '20260315', 'type': 'done', 'text': 'Daily task'
    }).get_json()

    assert 'next_entry' in body
    next_entry = body['next_entry']
    assert next_entry['date'] == '20260316'
    assert next_entry['type'] == 'todo'
    assert next_entry['recur_id'] == entry['recur_id']


def test_recurrence_stops_after_remaining_count(client):
    entry = client.post('/api/entries', json={
        'date': '20260315', 'type': 'todo', 'text': 'Last one',
        'recur_rule': 'daily', 'recur_remaining': 1
    }).get_json()

    body = client.put(f'/api/entries/{entry["id"]}', json={
        'date': '20260315', 'type': 'done', 'text': 'Last one'
    }).get_json()

    assert 'next_entry' not in body


def test_move_entry_swaps_priority(client):
    client.post('/api/entries', json={'date': '20260315', 'type': 'todo', 'text': 'First'})
    second = client.post('/api/entries', json={'date': '20260315', 'type': 'todo', 'text': 'Second'}).get_json()

    resp = client.post(f'/api/entries/{second["id"]}/move', json={'direction': 'up'})
    assert resp.status_code == 200

    todos = [e for e in resp.get_json() if e['type'] == 'todo']
    assert [e['text'] for e in todos] == ['Second', 'First']


def test_move_entry_at_boundary(client):
    entry = client.post('/api/entries', json={'date': '20260315', 'type': 'todo', 'text': 'Only'}).get_json()

    resp = client.post(f'/api/entries/{entry["id"]}/move', json={'direction': 'up'})
    assert resp.status_code == 200
    assert resp.get_json() == {'message': 'Already at boundary'}


def test_delete_entry_single(client):
    entry = client.post('/api/entries', json={'date': '20260315', 'type': 'todo', 'text': 'Bye'}).get_json()

    resp = client.delete(f'/api/entries/{entry["id"]}')
    assert resp.status_code == 200
    assert resp.get_json() == {'deleted': entry['id'], 'scope': 'single'}

    assert client.get('/api/entries?date=20260315').get_json() == []


def test_delete_entry_not_found(client):
    resp = client.delete('/api/entries/999')
    assert resp.status_code == 404


def test_delete_recurring_series_with_scope_all(client):
    entry = client.post('/api/entries', json={
        'date': '20260315', 'type': 'todo', 'text': 'Recurring', 'recur_rule': 'daily'
    }).get_json()

    promoted = client.put(f'/api/entries/{entry["id"]}', json={
        'date': '20260315', 'type': 'done', 'text': 'Recurring'
    }).get_json()
    next_entry = promoted['next_entry']

    resp = client.delete(f'/api/entries/{next_entry["id"]}?scope=all')
    assert resp.status_code == 200
    assert resp.get_json()['scope'] == 'all'

    # Both the now-done original and the spawned next occurrence share
    # the recur_id, so scope=all should remove them both.
    assert client.get('/api/entries?from=20260301&to=20260401').get_json() == []


def test_classify_values_saved_and_listed(client):
    client.post('/api/entries', json={
        'date': '20260315', 'type': 'todo', 'text': 'Tagged', 'classify': 'Work'
    })
    client.post('/api/entries', json={
        'date': '20260316', 'type': 'todo', 'text': 'Tagged2', 'classify': 'Home'
    })

    resp = client.get('/api/classify')
    assert resp.status_code == 200
    values = resp.get_json()
    assert set(values) >= {'Work', 'Home'}
    assert values == sorted(values)

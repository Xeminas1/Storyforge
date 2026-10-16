"""Adversarial regressions from the independent GM-pipeline review.

Scripted local replies isolate storage, context and evidence behavior. They do
not establish the quality or speed of an installed language model.
"""
import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine


def fact(text):
    return {'text': text, 'evidence': text}


def reply(narration, updates=None):
    def chat(_messages, _model):
        return json.dumps({'narration': narration, 'state_updates': updates or {}})
    # Exercise the same state-evidence requirement as the real transport.
    chat.requires_state_evidence = True
    return chat


class GMReviewRegressions(unittest.TestCase):
    def setUp(self):
        temporary = self.enterContext(tempfile.TemporaryDirectory())
        self.con = engine.open_db(Path(temporary) / 'review.db')
        self.addCleanup(self.con.close)
        self.world = engine.make_world(self.con, {
            'title': 'River Gate', 'description': 'A sentry guards the harbour gate.'})
        self.campaign = engine.new_campaign(self.con, {
            'world_id': self.world['id'], 'pc_name': 'Xeminas'})
        self.cid = self.campaign['id']

    def play(self, narration, updates=None, action='I listen.', cid=None):
        return engine.play_turn(self.con, cid or self.cid, action,
                                chat=reply(narration, updates))

    def dump(self):
        return list(self.con.iterdump())

    def seed_removable_memory(self):
        removed = 'Mara guards the brass gate.'
        kept = 'A courier waits beside the river.'
        self.play(removed + ' ' + kept, {
            'scene_memory': {'events': [fact(removed), fact(kept)]}})
        latest = self.play('A bell sounds from the tower.')
        return removed, kept, latest['messages'][-1]['id']

    def test_removed_memory_does_not_return_when_retrying_a_later_turn(self):
        removed, kept, latest = self.seed_removable_memory()
        result = engine.remove_scene_memory(self.con, self.cid, 'events', 0, removed)
        self.assertEqual(result['state']['scene_memory']['events'], [kept])
        result = engine.retry_message(self.con, self.cid, latest,
                                      chat=reply('The sentry studies the clouds.'))
        self.assertEqual(result['state']['scene_memory']['events'], [kept])
        self.assertEqual(len(result['messages']), 4)
        self.assertIn('Mara guards the brass gate.', result['messages'][1]['content'])

    def test_removed_memory_does_not_return_when_deleting_a_later_turn(self):
        removed, kept, latest = self.seed_removable_memory()
        engine.remove_scene_memory(self.con, self.cid, 'events', 0, removed)
        result = engine.delete_message(self.con, self.cid, latest)
        self.assertEqual(result['state']['scene_memory']['events'], [kept])
        self.assertEqual(result['messages'][-1]['role'], 'player')

    def test_memory_removal_preserves_other_categories_and_campaigns(self):
        text = 'Mara guards the brass gate.'
        npc = {'name': 'Mara', 'fact': text, 'evidence': text}
        self.play(text, {'scene_memory': {'events': [fact(text)], 'npcs': [npc]}})
        other = engine.new_campaign(self.con, {
            'world_id': self.world['id'], 'pc_name': 'Wren'})
        self.play(text, {'scene_memory': {'events': [fact(text)]}}, cid=other['id'])
        other_before = engine.get_campaign(self.con, other['id'])
        result = engine.remove_scene_memory(self.con, self.cid, 'events', 0, text)
        self.assertEqual(result['state']['scene_memory']['events'], [])
        self.assertEqual(result['state']['scene_memory']['npcs'][0]['facts'], [text])
        self.assertEqual(engine.get_campaign(self.con, other['id']), other_before)

    def test_stale_memory_removal_does_not_mutate_campaign(self):
        self.seed_removable_memory()
        before = self.dump()
        with self.assertRaisesRegex(ValueError, 'changed'):
            engine.remove_scene_memory(self.con, self.cid, 'events', 0,
                                       'A different remembered event.')
        self.assertEqual(self.dump(), before)

    def large_context_fixture(self, with_lore=False):
        payload = {'title': 'Gate', 'description': 'A useful world premise. ' * 210}
        if with_lore:
            payload['sections'] = [
                {'title': 'Gate lore ' + str(i), 'kind': 'lore',
                 'content': 'A keeper guards the ancient gate. ' * 60}
                for i in range(12)]
        world = engine.make_world(self.con, payload)
        campaign = engine.new_campaign(self.con, {
            'world_id': world['id'], 'pc_name': 'Wren',
            'weaknesses': 'Wren cannot cross warded stone. ' * 55})
        return engine.get_campaign(self.con, campaign['id']), world

    def test_optional_inventory_cannot_crowd_out_the_latest_scene_handoff(self):
        campaign, world = self.large_context_fixture()
        state = campaign['state']
        state['inventory'] = ['Ancient silver token number ' + str(i) for i in range(80)]
        prior = [
            {'role': 'player', 'content': 'I study the gate. ' * 140},
            {'role': 'gm', 'content': 'Mara closes the gate and waits.'}]
        before = copy.deepcopy(state)
        # The required records and latest turn fit without optional inventory.
        control = engine.build_gm_context(self.con, campaign, world, 'I listen.',
                                          prior, {**state, 'inventory': []})
        self.assertIn(prior[-1]['content'], str(control['messages']))
        actual = engine.build_gm_context(self.con, campaign, world, 'I listen.', prior, state)
        contents = '\n'.join(message['content'] for message in actual['messages'])
        self.assertIn(prior[-1]['content'], contents)
        self.assertIn(prior[0]['content'], contents)
        self.assertIn(world['description'], contents)
        self.assertIn(campaign['pc_profile']['weaknesses'], contents)
        self.assertEqual(state, before)
        self.assertLessEqual(actual['context']['prompt_bytes']
                             + actual['context']['repair_bytes_reserved'],
                             engine.GM_CONTEXT_BYTE_LIMIT)

    def test_many_agency_violations_cannot_overflow_the_second_request_budget(self):
        campaign, world = self.large_context_fixture(with_lore=True)
        # Independent concrete actions, rather than deriving examples from the
        # guard's implementation; this previously yielded a 17,480-byte repair.
        verbs = ('raise draw summon cast strike attack bow nod smile walk step grin '
                 'reach kneel turn point lift choose decide threaten continue say '
                 'speak declare reply whisper tell look accept agree promise enter '
                 'leave follow take give sign refuse trust answer ask watch sit '
                 'stand embrace kiss swear shout mutter announce command let '
                 'reveal confess').split()
        invalid = ' '.join('You ' + verb + ' the seal.' for verb in verbs)
        calls = []

        def chat(messages, _model):
            calls.append(copy.deepcopy(messages))
            narration = invalid if len(calls) == 1 else 'A sentry studies the gate.'
            return json.dumps({'narration': narration, 'state_updates': {}})

        narration, _ = engine._generate_turn(self.con, campaign, world, 'I listen.',
                                            [], campaign['state'], chat=chat)
        self.assertIn('A sentry studies the gate.', narration)
        self.assertEqual(len(calls), 2)
        for messages in calls:
            self.assertLessEqual(sum(len(message['content'].encode('utf-8'))
                                     for message in messages), engine.GM_CONTEXT_BYTE_LIMIT)
        self.assertIn('I listen.', calls[-1][-1]['content'])
        self.assertFalse(any(message['role'] == 'assistant' and invalid in message['content']
                             for message in calls[-1]))

    def test_whitespace_cannot_store_the_player_as_an_npc(self):
        text = 'Xeminas stands at the gate.'
        before = self.dump()
        with self.assertRaisesRegex(ValueError, 'Nothing was saved'):
            self.play(text, {'scene_memory': {'npcs': [
                {'name': ' Xeminas ', 'fact': text, 'evidence': text}]}},
                action='I stand at the gate.')
        self.assertEqual(self.dump(), before)

    def test_a_genuine_npc_with_outer_whitespace_can_be_remembered(self):
        text = 'Mara guards the gate.'
        result = self.play(text, {'scene_memory': {'npcs': [
            {'name': ' Mara ', 'fact': text, 'evidence': text}]}})
        self.assertEqual(result['state']['scene_memory']['npcs'], [
            {'name': 'Mara', 'facts': [text]}])

    def seed_open_threads(self):
        thread = 'A sealed letter awaits an answer.'
        other = 'The storehouse door remains locked.'
        self.play(thread + ' ' + other, {'scene_memory': {
            'open_threads': [fact(thread), fact(other)]}})
        return thread, other

    def test_unrelated_narration_cannot_resolve_an_open_thread(self):
        thread, _ = self.seed_open_threads()
        before = self.dump()
        with self.assertRaisesRegex(ValueError, 'Nothing was saved'):
            self.play('A raven calls above the quay.', {'scene_memory': {
                'resolve_threads': [{'text': thread, 'evidence': 'A raven calls above the quay.'}]}})
        self.assertEqual(self.dump(), before)

    def test_explicitly_withdrawn_exact_thread_can_be_resolved(self):
        thread, other = self.seed_open_threads()
        text = ('The keeper withdraws the request labelled "' + thread
                + '"; no answer is required now.')
        result = self.play(text, {'scene_memory': {
            'resolve_threads': [{'text': thread, 'evidence': text}]}})
        self.assertEqual(result['state']['scene_memory']['open_threads'], [other])

    def test_actual_model_policy_explains_body_only_state_evidence(self):
        calls = []

        def chat(messages, model):
            calls.append(copy.deepcopy(messages))
            return reply('A sentry watches the river.')(messages, model)

        engine.play_turn(self.con, self.cid, 'I listen.', chat=chat)
        policy = calls[0][0]['content']
        self.assertRegex(policy, re.compile(
            r'(?:prose body|body of (?:the )?narration|body-only)', re.I))
        self.assertRegex(policy, re.compile(
            r'(?:header[^\n]{0,100}(?:not|never|insufficient|exclude)|'
            r'(?:not|never|exclude)[^\n]{0,100}header)', re.I))

    def test_header_only_evidence_is_rejected_without_saving(self):
        header = '[Ash Quay - Veyr - Dusk]'
        before = self.dump()
        with self.assertRaisesRegex(ValueError, 'Nothing was saved'):
            self.play(header + '\n\nA sentry watches the river.', {
                'location': 'Ash Quay', 'parent_area': 'Veyr', 'time_of_day': 'Dusk',
                'evidence': {field: header for field in
                             ('location', 'parent_area', 'time_of_day')}})
        self.assertEqual(self.dump(), before)

    def test_body_evidence_can_establish_the_scene_fields(self):
        body = 'At Ash Quay in Veyr, Dusk settles over the river.'
        result = self.play('[Ash Quay - Veyr - Dusk]\n\n' + body, {
            'location': 'Ash Quay', 'parent_area': 'Veyr', 'time_of_day': 'Dusk',
            'evidence': {field: body for field in
                         ('location', 'parent_area', 'time_of_day')}})
        for field, expected in (('location', 'Ash Quay'), ('parent_area', 'Veyr'),
                                ('time_of_day', 'Dusk')):
            self.assertEqual(result['state'][field], expected)
        self.assertNotIn('evidence', result['state'])


if __name__ == '__main__':
    unittest.main()

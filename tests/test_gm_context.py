"""Actual GM request context stays bounded without losing rules or scene handoff."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine


class GMContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = engine.open_db(Path(self.tmp.name) / 'campaign.db')
        self.world = engine.make_world(self.con, {'title': 'Lantern Coast',
            'description': 'Start at the station. Later attend the council; attendance remains optional.',
            'sections': [{'title': 'Maribel', 'kind': 'npc',
                          'content': 'Maribel keeps the brass observatory keys.'}]})
        self.campaign = engine.new_campaign(self.con, {'world_id': self.world['id'],
            'pc_name': 'Wren', 'starting_location': 'Station', 'abilities': ['Shadow Step']})

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def capture(self, action='I wait.', prior=None, state=None, feedback=''):
        calls = []
        def chat(messages, model):
            calls.append(copy.deepcopy(messages))
            return json.dumps({'narration': 'A porter checks the arrival board.', 'state_updates': {}})
        campaign = engine.get_campaign(self.con, self.campaign['id'])
        engine._generate_turn(self.con, campaign, self.world, action, prior or [],
                              state or campaign['state'], feedback=feedback, chat=chat)
        return calls[0]

    def block(self, system, start, end):
        return json.loads(system.split(start, 1)[1].split(end, 1)[0])

    def test_latest_journal_and_scene_fields_survive_large_saved_state(self):
        state = engine.get_campaign(self.con, self.campaign['id'])['state']
        state.update(parent_area='Coast', time_of_day='Dusk',
                     journal=[f'The courier delivers parcel number {n}. ' * 7 for n in range(150)])
        state['inventory'] = [f'Ancient token number {n}' for n in range(100)]
        before = copy.deepcopy(state)
        system = self.capture(state=state)[0]['content']
        selected = self.block(system,
            'ESTABLISHED CAMPAIGN STATE (journal entries screened for player agency):\n',
            '\nRELEVANT SAVED WORLD LORE')
        self.assertEqual(selected['location'], 'Station')
        self.assertEqual(selected['parent_area'], 'Coast')
        self.assertEqual(selected['time_of_day'], 'Dusk')
        self.assertIn(state['journal'][-1], selected['journal'])
        self.assertEqual(state, before)

    def test_latest_complete_gm_handoff_is_not_lost_after_1100_characters(self):
        ending = 'Maribel gives the sealed warrant to the prefect; the gate is now closed.'
        prior = [{'role': 'gm', 'content': ('The porter discusses the weather. ' * 50) + '\n\n' + ending}]
        messages = self.capture(prior=prior)
        self.assertIn(ending, '\n'.join(m['content'] for m in messages[1:]))
        self.assertTrue(any(m['role'] == 'assistant' and m['content'] == prior[0]['content'] for m in messages))

    def test_requested_ability_keeps_full_effect_cost_and_limits(self):
        records = engine.get_campaign(self.con, self.campaign['id'])['pc_profile']['ability_details']
        records[0].update(effect='Move between nearby shadows. ' * 80,
            visual='Shadows coil around the caster. ' * 30,
            cost='Ten mana', limitations='No passage through warded stone; no unwilling passenger.')
        engine.save_campaign_abilities(self.con, self.campaign['id'], records)
        system = self.capture(action='I cast Shadow Step.')[0]['content']
        self.assertIn(records[0]['effect'].strip(), system)
        self.assertIn(records[0]['limitations'], system)
        self.assertIn('Ten mana', system)
        spells = self.block(system,
            'CANONICAL CHARACTER SPELLS & ABILITIES (do not invent effects):\n',
            '\nESTABLISHED CAMPAIGN STATE')
        self.assertEqual(spells[0]['limitations'], records[0]['limitations'])

    def test_free_form_ability_description_retrieves_complete_relevant_rules(self):
        records = engine.get_campaign(self.con, self.campaign['id'])['pc_profile']['ability_details']
        records[0].update(effect='Teleport between nearby shadows.', cost='Ten mana',
                          limitations='No passage through warded stone.')
        engine.save_campaign_abilities(self.con, self.campaign['id'], records)
        system = self.capture(action='I teleport through the shadows.')[0]['content']
        self.assertIn('Teleport between nearby shadows.', system)
        self.assertIn('Ten mana', system)
        self.assertIn('No passage through warded stone.', system)

    def test_actual_request_has_one_action_copy_and_overall_character_bound(self):
        action = 'I inspect UNIQUE_ACTION_SENTINEL on the sealed parcel.'
        state = engine.get_campaign(self.con, self.campaign['id'])['state']
        state['journal'] = ['The porter delivers a different sealed parcel. ' * 7 for _ in range(150)]
        prior = []
        for n in range(4):
            prior.extend([{'role': 'player', 'content': f'I watch porter number {n}. ' * 40},
                {'role': 'gm', 'content': 'The porter discusses the station timetable. ' * 45}])
        messages = self.capture(action, prior=prior, state=state)
        content = '\n'.join(m['content'] for m in messages)
        self.assertEqual(content.count('UNIQUE_ACTION_SENTINEL'), 1)
        self.assertLessEqual(sum(len(m['content']) for m in messages), 16000)

    def test_context_composition_does_not_change_saved_campaign(self):
        before = list(self.con.iterdump())
        self.capture()
        self.assertEqual(list(self.con.iterdump()), before)

    def test_large_world_keeps_full_premise_and_complete_latest_ending(self):
        premise = ('Start at the station and later visit the council. ' * 110)[:4950]
        self.world = engine.make_world(self.con, {'title': 'A large world', 'description': premise,
            'sections': [{'title': f'Council record {n}', 'kind': 'lore',
                          'content': 'The council works at the station. ' * 70} for n in range(20)]})
        prior = [{'role': 'gm', 'content': 'The porter discusses the weather. ' * 320
                   + '\n\nMaribel closes the brass gate and waits beside the warrant.'}]
        messages = self.capture(prior=prior)
        self.assertIn(self.world['description'], messages[0]['content'])
        latest = next(m['content'] for m in messages if m['role'] == 'assistant')
        self.assertIn('Earlier narration omitted', latest)
        self.assertTrue(latest.endswith('Maribel closes the brass gate and waits beside the warrant.'))
        self.assertLessEqual(sum(len(m['content']) for m in messages) + 1200 + len('I wait.'), 16000)

    def test_oversize_required_ability_rules_fail_before_contact_or_save(self):
        records = engine.get_campaign(self.con, self.campaign['id'])['pc_profile']['ability_details']
        records[0].update(effect='A' * 2400, limitations='B' * 1400)
        records.extend([{**records[0], 'id': engine.new_id(), 'name': f'Power {n}'} for n in range(4)])
        engine.save_campaign_abilities(self.con, self.campaign['id'], records)
        before = list(self.con.iterdump())
        calls = []
        with self.assertRaisesRegex(ValueError, 'too large.*Nothing was saved'):
            engine.play_turn(self.con, self.campaign['id'],
                'I use Shadow Step, Power 0, Power 1, Power 2 and Power 3.',
                chat=lambda *args: calls.append(args))
        self.assertEqual(calls, [])
        self.assertEqual(list(self.con.iterdump()), before)

    def test_oversize_unicode_premise_fails_before_contact_or_save(self):
        world = engine.make_world(self.con, {'title': 'Station', 'description': '\u754c' * 5000})
        campaign = engine.new_campaign(self.con, {'world_id': world['id'], 'pc_name': 'Wren'})
        before = list(self.con.iterdump())
        calls = []
        with self.assertRaisesRegex(ValueError, 'too large.*Nothing was saved'):
            engine.play_turn(self.con, campaign['id'], 'I wait.', chat=lambda *args: calls.append(args))
        self.assertEqual(calls, [])
        self.assertEqual(list(self.con.iterdump()), before)

    def test_multilingual_context_counts_utf8_bytes_and_keeps_the_handoff(self):
        campaign = engine.get_campaign(self.con, self.campaign['id'])
        world = {**self.world, 'description': '\u99c5\u306e\u7269\u8a9e\u3002' * 500}
        ending = '\u4fe1\u4f7f\u628a\u94a5\u5319\u4ea4\u7ed9\u5b88\u536b\u3002'
        prior = [{'role': 'gm', 'content': '\u98ce\u5439\u8fc7\u8f66\u7ad9\u3002' * 900 + '\n\n' + ending}]
        built = engine.build_gm_context(self.con, campaign, world, 'I wait.', prior, campaign['state'])
        measured = sum(len(message['content'].encode('utf-8')) for message in built['messages'])
        self.assertEqual(measured, built['context']['prompt_bytes'])
        self.assertLessEqual(measured + built['context']['repair_bytes_reserved'], built['context']['byte_limit'])
        self.assertTrue(next(m['content'] for m in built['messages'] if m['role'] == 'assistant').endswith(ending))

    def test_memory_is_in_valid_state_and_no_input_records_are_mutated(self):
        state = engine.get_campaign(self.con, self.campaign['id'])['state']
        state['scene_memory'] = {'summary': 'Maribel guards the gate.',
            'npcs': [{'name': 'Maribel', 'facts': ['Maribel keeps the brass key.']}],
            'open_threads': ['The sealed warrant remains unopened.'],
            'events': ['The brass gate was closed.']}
        before = copy.deepcopy(state)
        system = self.capture(state=state)[0]['content']
        selected = self.block(system,
            'ESTABLISHED CAMPAIGN STATE (journal entries screened for player agency):\n',
            '\nRELEVANT SAVED WORLD LORE')
        self.assertEqual(selected['scene_memory']['npcs'], state['scene_memory']['npcs'])
        self.assertEqual(state, before)

    def test_preview_reports_the_same_budgeted_lore_as_actual_context(self):
        campaign = engine.get_campaign(self.con, self.campaign['id'])
        built = engine.build_gm_context(self.con, campaign, self.world, '', [], campaign['state'])
        preview = engine.preview_campaign_lore(self.con, campaign['id'])
        self.assertEqual(preview['selected_entries'], built['lore_entries'])
        self.assertEqual(preview['context'], built['context'])
        self.assertIn('not exact model tokens', preview['notice'])


if __name__ == '__main__':
    unittest.main()

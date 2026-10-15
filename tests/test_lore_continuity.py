"""Saved creator canon, useful excerpts and current-scene retrieval regressions."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine


class LoreContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.con = engine.open_db(Path(self.temp.name) / 'test.db')

    def tearDown(self):
        self.con.close()
        self.temp.cleanup()

    def reference(self, title, summary):
        return engine.as_sections([{
            'title': title, 'summary': summary, 'kind': 'lore',
            'url': 'https://en.wikipedia.org/?curid=12345',
        }])[0]

    def test_matching_creator_canon_precedes_more_lexically_similar_reference(self):
        creator = {'title': 'Local rule', 'kind': 'lore',
                   'content': 'Elmbridge waives its bridge toll for all travellers.'}
        reference = self.reference('Elmbridge bridge toll river',
                                   'Elmbridge bridge demands a toll from all travellers.')
        selected = engine.select_lore_entries([reference, creator],
                                             'Elmbridge bridge toll river', max_entries=1)
        self.assertEqual(selected[0]['title'], 'Local rule')

    def test_unrelated_creator_entry_does_not_hide_relevant_reference(self):
        creator = {'title': 'Frozen meadow', 'kind': 'location', 'content': 'Empty fields of snow.'}
        reference = self.reference('Elmbridge', 'A bridge across the river.')
        selected = engine.select_lore_entries([creator, reference], 'Elmbridge', max_entries=1)
        self.assertEqual(selected[0]['title'], 'Elmbridge')

    def test_unmatched_overview_bonus_cannot_hide_matching_reference(self):
        overview = {'title': 'Overview', 'kind': 'lore', 'content': 'A frozen realm.'}
        reference = self.reference('Elmbridge', 'A bridge across the river.')
        selected = engine.select_lore_entries([overview, reference], 'Elmbridge', max_entries=1)
        self.assertEqual(selected[0]['title'], 'Elmbridge')

    def test_matching_fact_beyond_opening_excerpt_reaches_model(self):
        sections = [{'title': 'City gates', 'kind': 'location',
                     'content': ('Stonemasons maintain the ancient walls. ' * 70
                                 + '\n\nThe Moon Gate is sealed until dawn.\n\n'
                                 + 'The streets have many houses. ' * 50)}]
        rendered = engine.pick_sections(sections, 'Moon Gate', max_characters=600)
        self.assertIn('The Moon Gate is sealed until dawn.', rendered)
        self.assertLessEqual(len(rendered), 600)

    def test_matching_sentence_keeps_negation_before_long_qualifier(self):
        sentence = ('The council does not permit '
                    + 'any of the old and historically contentious ' * 5
                    + 'Moon Gate mechanisms to operate before dawn.')
        sections = [{'title': 'City gates', 'kind': 'location',
                     'content': ('Harbour warehouses hold grain. ' * 50 + sentence
                                 + ' The tide remains low. ' * 50)}]
        rendered = engine.pick_sections(sections, 'Moon Gate', max_characters=450)
        self.assertIn(sentence, rendered)
        self.assertLessEqual(len(rendered), 450)

    def test_overlong_matching_sentence_is_omitted_instead_of_reversing_meaning(self):
        sentence = ('The council does not permit ' + 'an exceptionally old mechanism, ' * 50
                    + 'the Moon Gate, to operate before dawn.')
        sections = [{'title': 'City gates', 'kind': 'location',
                     'content': 'The harbour is quiet. ' * 50 + sentence}]
        rendered = engine.pick_sections(sections, 'Moon Gate', max_characters=350)
        self.assertNotIn('Moon Gate', rendered)
        self.assertLessEqual(len(rendered), 350)

    def test_three_letter_names_match_whole_words_not_longer_names(self):
        sections = [
            {'title': 'Ashford', 'kind': 'location', 'content': 'An unrelated northern town.'},
            {'title': 'Ash', 'kind': 'npc', 'content': 'The harbour ferryman.'},
        ]
        selected = engine.select_lore_entries(sections, 'I speak to Ash', max_entries=1)
        self.assertEqual(selected[0]['title'], 'Ash')

    def test_reference_provenance_survives_excerpt_and_exact_context_budget(self):
        sections = [self.reference('Elmbridge', 'Elmbridge is a bridge. ' * 100)]
        snapshot = copy.deepcopy(sections)
        rendered = engine.pick_sections(sections, 'Elmbridge', max_characters=350)
        self.assertIn('PUBLIC REFERENCE', rendered)
        self.assertIn('Source: https://en.wikipedia.org/?curid=12345', rendered)
        self.assertLessEqual(len(rendered), 350)
        self.assertEqual(sections, snapshot)

    def test_attributed_creator_lore_keeps_creator_priority(self):
        sections = [{'title': 'Elmbridge', 'kind': 'location',
                     'content': 'Elmbridge has no toll.\nSource: https://creator.example/world'}]
        rendered = engine.pick_sections(sections, 'Elmbridge')
        self.assertIn('CREATOR CANON', rendered)
        self.assertNotIn('PUBLIC REFERENCE', rendered)

    def test_short_action_keeps_latest_scene_lore_in_actual_request(self):
        sections = [
            *[{'title': f'Opening pier {n}', 'kind': 'location',
               'content': 'The opening pier welcomes new arrivals.'} for n in range(12)],
            {'title': 'Maribel', 'kind': 'npc', 'content': 'Maribel keeps the brass observatory keys.'},
        ]
        world = engine.make_world(self.con, {
            'title': 'The Coast', 'description': 'Start at the opening pier. Later visit the observatory.',
            'sections': sections,
        })
        campaign = engine.new_campaign(self.con, {'world_id': world['id'], 'pc_name': 'Wren'})
        with self.con:
            self.con.execute('INSERT INTO messages (campaign_id,role,content,created_at) VALUES (?,?,?,?)',
                             (campaign['id'], 'gm', 'Maribel waits beneath the brass telescope.', engine.now()))
        sent = []

        def chat(messages, model):
            sent.append(messages)
            return json.dumps({'narration': 'The telescope ticks as its mechanism turns.', 'state_updates': {}})

        engine.play_turn(self.con, campaign['id'], 'I wait', chat=chat)
        self.assertIn('Maribel keeps the brass observatory keys.', sent[0][0]['content'])
        self.assertIn('CREATOR CANON', sent[0][0]['content'])
        self.assertIn('do not restart', sent[0][0]['content'].lower())

    def test_suspect_legacy_prose_does_not_bias_preview_or_actual_retrieval(self):
        sections = [
            *[{'title': f'Eastbank street {n}', 'kind': 'location',
               'content': 'Eastbank is a peaceful village.'} for n in range(12)],
            {'title': 'Zarvok', 'kind': 'npc', 'content': 'Zarvok watches the abandoned cemetery.'},
        ]
        world = engine.make_world(self.con, {
            'title': 'The Coast', 'description': 'Start at Eastbank.', 'sections': sections,
        })
        campaign = engine.new_campaign(self.con, {
            'world_id': world['id'], 'pc_name': 'Wren', 'starting_location': 'Eastbank',
        })
        suspect = 'You decide to follow Zarvok into the cemetery.'
        with self.con:
            self.con.execute('INSERT INTO messages (campaign_id,role,content,created_at) VALUES (?,?,?,?)',
                             (campaign['id'], 'gm', suspect, engine.now()))
        preview = engine.preview_campaign_lore(self.con, campaign['id'])
        self.assertNotIn('Zarvok', [entry['title'] for entry in preview['selected_entries']])
        sent = []

        def chat(messages, model):
            sent.append(messages)
            return json.dumps({'narration': 'A gull circles above the rooftops.', 'state_updates': {}})

        engine.play_turn(self.con, campaign['id'], 'I wait', chat=chat)
        self.assertNotIn('Zarvok', sent[0][0]['content'])
        self.assertEqual(engine.get_messages(self.con, campaign['id'])[0]['content'], suspect)

    def test_all_saved_premise_is_included_and_plans_are_not_completed_events(self):
        premise = 'An island of quiet villages. ' * 130 + 'The final milestone is the Lantern Council.'
        context = engine.world_scenario_context({'title': 'The Coast', 'description': premise})
        self.assertIn('The final milestone is the Lantern Council.', context)
        self.assertIn('planned', context.lower())
        self.assertIn('public references', context.lower())


if __name__ == '__main__':
    unittest.main()

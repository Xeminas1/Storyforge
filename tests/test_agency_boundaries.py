"""Adversarial player-ownership checks, with controls for ordinary free-form play.

These fixtures describe identifiable claims; they do not establish that a
heuristic validator can understand every possible natural-language sentence.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine


def reply(narration, **changes):
    return json.dumps({'narration': narration, 'state_updates': changes})


class PlayerOwnershipTests(unittest.TestCase):
    def test_coordinated_authored_actions_and_third_person_acknowledgements(self):
        for narration in ('You look at the figure and raise your hand.',
                          'You look at the figure. Xeminas raises his hand.',
                          'You raise your hand as the guard watches.'):
            with self.subTest(narration=narration):
                self.assertEqual(engine.player_agency_violations(
                    narration,'Xeminas','I look at the figure and raise my hand.'),[])

    def test_another_characters_hand_is_not_the_players_hand(self):
        self.assertTrue(engine.player_agency_violations(
            'You raise your hand.','Xeminas','I raise his hand.'))
        self.assertTrue(engine.player_agency_violations(
            'You raise his hand.','Xeminas','I raise my hand.'))

    def test_attributed_npc_dialogue_documents_and_shouting_remain_available(self):
        for narration in ('The guard tells you, "I am the gatekeeper."',
                          'The guard says to you, "I am the gatekeeper."',
                          'The guard says softly, "I am the gatekeeper."',
                          '"I am the gatekeeper," says the guard.',
                          'The sign reads, "I seek able travellers for a task."',
                          'A notice reads *I seek able travellers for a task.*',
                          'The guard shouts **LEAVE ME ALONE!**'):
            with self.subTest(narration=narration):
                self.assertEqual(engine.player_agency_violations(narration,'Xeminas','I watch the guard.'),[])

    def test_emphasis_and_inverted_attribution_cannot_hide_player_authorship(self):
        for narration in ('You say *I pledge loyalty to the king.*',
                          'You softly say "I pledge loyalty to the king."',
                          '"I pledge loyalty to the king," says Xeminas.',
                          '*You raise your hand.*'):
            with self.subTest(narration=narration):
                self.assertTrue(engine.player_agency_violations(narration,'Xeminas','I say "Hello."'))

    def test_unrequested_dialogue_actions_and_private_thoughts_are_rejected(self):
        examples = {
            'named thought': 'Xeminas believes the stranger is trustworthy.',
            'possessive thought': 'Your certainty that the stranger can be trusted grows.',
            'passive decision': 'The oath is accepted by Xeminas.',
            'single-quoted dialogue': "'I serve the king,' Xeminas answers.",
            'speaker label': 'Xeminas: "I serve the king."',
            'compound action': 'You look at the figure and raise your hand.',
            'indirect speech': 'Your promise to serve the king reassures the guard.',
            'perfect-tense choice': 'You have chosen Slytherin.',
        }
        for label, narration in examples.items():
            with self.subTest(label=label):
                self.assertTrue(
                    engine.player_agency_violations(narration, 'Xeminas', 'I look at the figure.'),
                    narration,
                )

    def test_mentioned_verbs_do_not_authorize_a_different_player_action(self):
        examples = {
            'negative': 'I do not raise my hand.',
            'other actor': 'I watch the guard raise his hand.',
            'other actor compound': 'I watch the guard nod and raise his hand.',
            'different object': 'I raise an eyebrow.',
        }
        for label, action in examples.items():
            with self.subTest(label=label):
                self.assertTrue(
                    engine.player_agency_violations('You raise your hand.', 'Xeminas', action),
                    action,
                )

    def test_authorized_player_actions_and_exact_dialogue_remain_allowed(self):
        examples = [
            ('I raise my hand.', 'You raise your hand.'),
            ('I smile and continue on.', 'You smile and continue on.'),
            ('I say "I am Xeminas."', '"I am Xeminas," you say.'),
            ('I shout "Leave me alone!"', '"Leave me alone!" you shout.'),
            ('I feel curious about the stranger.', 'You feel curious about the stranger.'),
        ]
        for action, narration in examples:
            with self.subTest(action=action):
                self.assertEqual(engine.player_agency_violations(narration, 'Xeminas', action), [])

    def test_speech_authorization_does_not_grant_extra_dialogue(self):
        self.assertTrue(engine.player_agency_violations(
            '"I pledge my loyalty to the king," you say.',
            'Xeminas', 'I say "Good evening."',
        ))

    def test_player_dialogue_possessives_cannot_be_rewritten(self):
        self.assertTrue(engine.player_agency_violations(
            '"I serve your king," you say.', 'Xeminas', 'I say "I serve my king."',
        ))

    def test_continuing_one_action_does_not_authorize_new_travel(self):
        self.assertTrue(engine.player_agency_violations(
            'You continue into the castle.', 'Xeminas', 'I continue watching the guard.',
        ))

    def test_world_effects_observations_npc_speech_and_invitations_are_allowed(self):
        examples = [
            'The guard pushes you backwards.',
            'You hear a bell and see a lantern beside the gate.',
            '“I am the guard,” the sentry says, reaching for his whistle.',
            'The sentry says, "I will raise my hand when the gate opens."',
            'The guard asks whether you will raise your hand.',
            'If you raise your hand, the guard will see the signet.',
            'You can raise your hand to signal the guard.',
        ]
        for narration in examples:
            with self.subTest(narration=narration):
                self.assertEqual(engine.player_agency_violations(narration, 'Xeminas', 'I watch.'), [])


class AgencyPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = engine.open_db(Path(self.tmp.name) / 'storyforge.db')
        world = engine.make_world(self.db, {
            'title': 'The Lantern Court', 'description': 'A river gate watched by a sentry.',
        })
        self.campaign = engine.new_campaign(self.db, {'world_id': world['id'], 'pc_name': 'Xeminas'})
        self.cid = self.campaign['id']

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def snapshot(self):
        """Include checkpoints and correction history, not only visible prose."""
        return {
            table: [tuple(row) for row in self.db.execute('SELECT * FROM ' + table + ' ORDER BY rowid')]
            for table in ('campaigns', 'messages', 'turn_checkpoints', 'gm_feedback')
        }

    def turn(self, action, narration, **changes):
        return engine.play_turn(self.db, self.cid, action, chat=lambda *_: reply(narration, **changes))

    def test_invented_journal_belief_is_corrected_before_any_save(self):
        calls = []
        responses = iter([
            reply('The sentry keeps watch.', journal_entry='Xeminas believes the sentry is trustworthy.'),
            reply('The sentry calls for the gatekeeper.', journal_entry='The sentry called for the gatekeeper.'),
        ])

        def chat(messages, model):
            calls.append(json.loads(json.dumps(messages)))
            return next(responses)

        result = engine.play_turn(self.db, self.cid, 'I watch the sentry.', chat=chat)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['state']['journal'], ['The sentry called for the gatekeeper.'])
        self.assertEqual(len(result['messages']), 2)
        self.assertIn('REWRITE THIS TURN', calls[1][-1]['content'])

    def test_player_claims_cannot_enter_other_textual_state_fields(self):
        false_claim = 'Xeminas believes the stranger is trustworthy.'
        examples = {
            'location': false_claim,
            'parent_area': false_claim,
            'time_of_day': false_claim,
            'inventory_add': [false_claim],
            'inventory_remove': [false_claim],
        }
        for field, value in examples.items():
            with self.subTest(field=field):
                before = self.snapshot()
                calls = []

                def chat(messages, model):
                    calls.append(messages)
                    return reply('The sentry keeps watch.', **{field: value})

                with self.assertRaisesRegex(ValueError, 'Nothing was saved'):
                    engine.play_turn(self.db, self.cid, 'I watch the sentry.', chat=chat)
                self.assertEqual(len(calls), 2)
                self.assertEqual(self.snapshot(), before)

    def test_ordinary_state_labels_and_inventory_outcomes_remain_supported(self):
        self.turn('I listen.', 'The sentry calls for the gatekeeper.', inventory_add=['gate token'])
        result = self.turn(
            'I inspect the archway.', 'The gatekeeper identifies the old archway.',
            location='River Gate', parent_area="The Dark Monarch's Marches", time_of_day='Dusk',
            inventory_add=['wax-sealed letter'], inventory_remove=['gate token'],
        )
        self.assertEqual(result['state']['location'], 'River Gate')
        self.assertEqual(result['state']['parent_area'], "The Dark Monarch's Marches")
        self.assertEqual(result['state']['time_of_day'], 'Dusk')
        self.assertEqual(result['state']['inventory'], ['wax-sealed letter'])

    def test_invalid_twice_preserves_campaign_messages_checkpoints_and_feedback(self):
        self.turn('I listen.', 'The sentry calls for the gatekeeper.', location='River Gate',
                  inventory_add=['gate token'], journal_entry='The sentry called for the gatekeeper.')
        before = self.snapshot()
        calls = []

        def chat(messages, model):
            calls.append(messages)
            return reply('Xeminas believes the stranger is trustworthy.', location='Throne Room',
                         inventory_remove=['gate token'], journal_entry='Xeminas accepts the oath.')

        with self.assertRaisesRegex(ValueError, 'Nothing was saved'):
            engine.play_turn(self.db, self.cid, 'I look at the stranger.', chat=chat)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.snapshot(), before)

    def test_failed_retry_preserves_original_and_later_dependent_turns(self):
        self.turn('I listen.', 'The sentry calls for the gatekeeper.', location='River Gate', inventory_add=['token'])
        target = engine.get_messages(self.db, self.cid)[-1]
        self.turn('I wait.', 'A gatekeeper opens a shutter.', journal_entry='A gatekeeper opened a shutter.')
        before = self.snapshot()

        with self.assertRaisesRegex(ValueError, 'Nothing was saved'):
            engine.retry_message(
                self.db, self.cid, target['id'], feedback='Do not act for Xeminas.',
                chat=lambda *_: reply('The oath is accepted by Xeminas.', inventory_remove=['token']),
            )
        self.assertEqual(self.snapshot(), before)

    def test_retry_with_prior_gm_history_keeps_context_and_checkpoints(self):
        self.turn('I listen.', 'The sentry calls for the gatekeeper.', location='River Gate', inventory_add=['token'])
        self.turn('I wait.', 'A gatekeeper opens a shutter.', journal_entry='A gatekeeper opened a shutter.')
        target = engine.get_messages(self.db, self.cid)[-1]
        calls = []

        def chat(messages, model):
            calls.append(messages)
            return reply('The gatekeeper asks the sentry for a lantern.', journal_entry='The gatekeeper requested a lantern.')

        result = engine.retry_message(self.db, self.cid, target['id'], chat=chat)
        self.assertEqual(len(result['messages']), 4)
        self.assertEqual(result['messages'][-2]['content'], 'I wait.')
        self.assertTrue(result['messages'][-1]['has_checkpoint'])
        self.assertEqual(result['state']['inventory'], ['token'])
        self.assertEqual(result['state']['journal'], ['The gatekeeper requested a lantern.'])
        self.assertTrue(any(m['role'] == 'assistant' and 'sentry calls' in m['content'] for m in calls[0]))

    def test_legacy_invented_journal_claim_is_withheld_without_changing_save(self):
        campaign = engine.get_campaign(self.db, self.cid)
        state = campaign['state']
        false_note = 'Xeminas believes the stranger is trustworthy.'
        true_note = 'The sentry called for the gatekeeper.'
        state['journal'] = [false_note, true_note]
        self.db.execute('UPDATE campaigns SET state_json=? WHERE id=?', (json.dumps(state), self.cid))
        self.db.commit()
        calls = []

        def chat(messages, model):
            calls.append(messages)
            return reply('The sentry watches the river.')

        result = engine.play_turn(self.db, self.cid, 'I watch the river.', chat=chat)
        self.assertNotIn(false_note, calls[0][0]['content'])
        self.assertIn(true_note, calls[0][0]['content'])
        self.assertEqual(result['state']['journal'], [false_note, true_note])


if __name__ == '__main__':
    unittest.main()

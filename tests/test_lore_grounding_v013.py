"""Ground world premises and important ceremonies rather than improvising them."""
import json
import tempfile
import unittest
from pathlib import Path
import engine

DESCRIPTION = ('Attend Hogwarts, choose your house, attend class, learn spells, and fight monsters '
               'and evil wizards. Start at Hogsmeade Station for the introduction and being able '
               'to sit through the Sorting Hat selection.')


class LoreGroundingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = engine.open_db(Path(self.temp.name)/'test.db')
        self.sections = [
            {'title':'Hogsmeade Station','kind':'location', 'content':'Trains terminate at Hogsmeade Station.'},
            {'title':'Hogwarts Sorting Ceremony','kind':'lore',
             'content':'In the Great Hall the Sorting Hat assigns students to houses.'},
            *[{'title':f'Unrelated creature number {n}', 'kind':'creature',
                'content':'A creature from another forest without a role in school life.'} for n in range(30)]
        ]
        self.world = engine.make_world(self.db,{'title':'Harry Potter: Wizarding World',
                                   'description':DESCRIPTION,'sections':self.sections})
        self.campaign=engine.new_campaign(self.db,{'world_id':self.world['id'], 'pc_name':'Xeminas'})
    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_world_premise_injected_even_with_separate_lore(self):
        sent=[]
        def fake(messages,model):
            sent.append(messages)
            return json.dumps({'narration':'A station porter checks arrivals.', 'state_updates':{}})
        engine.play_turn(self.db,self.campaign['id'],'I look at the figure',chat=fake)
        self.assertEqual(len(sent),1)
        context=sent[0][0]['content']
        self.assertIn('Start at Hogsmeade Station',context)
        self.assertIn('Hogwarts Sorting Ceremony',context)
        self.assertIn('Great Hall',context)
        self.assertIn('player can choose',context.lower())
        self.assertIn('not an earlier disembodied warning',context)

    def test_world_intro_prompts_start_and_future_milestones(self):
        captured=[]
        def fake(messages,model):
            captured.append(messages)
            return '{"narration":"The train doors open beside the station.","state_updates":{}}'
        engine.play_turn(self.db,self.campaign['id'],'__START__',chat=fake)
        self.assertIn('starting location prescribed by the world premise',captured[0][-1]['content'])
        self.assertIn('Hogsmeade Station',captured[0][0]['content'])

    def test_lore_preview_matches_turn_retrieval_and_is_bounded(self):
        preview=engine.preview_campaign_lore(self.db,self.campaign['id'])
        self.assertEqual(preview['premise'],DESCRIPTION)
        self.assertEqual(preview['total_saved_entries'],32)
        self.assertIn('Great Hall', preview['scenario_guidance'])
        self.assertLessEqual(len(preview['selected_entries']),8)
        self.assertIn('Hogwarts Sorting Ceremony',[x['title'] for x in preview['selected_entries']])
        self.assertEqual([x['title'] for x in preview['selected_entries']],
            [x['title'] for x in engine.select_lore_entries(self.sections,
             engine.world_lore_query(self.world,'',self.campaign['state'],[]))])

    def test_large_reference_cannot_crowd_out_ceremony(self):
        entries=[{'title':'Unrelated one','content':'ZZZ'*22000,'kind':'lore'},
            {'title':'Sorting Hat','content':'Four school houses named by a hat','kind':'lore'}]
        result=engine.select_lore_entries(entries,DESCRIPTION,max_characters=1450)
        self.assertEqual(result[0]['title'],'Sorting Hat')
        self.assertLessEqual(sum(len(x['content']) for x in result),1450)

    def test_unrelated_fantasy_not_given_hogwarts_rules(self):
        context=engine.world_scenario_context({'title':'Winter Keep','description':'Start at Frostford Bridge.'})
        self.assertIn('Start at Frostford Bridge',context)
        self.assertNotIn('SCENARIO CLARIFICATION',context)

if __name__=='__main__':unittest.main()

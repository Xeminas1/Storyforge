"""Regression tests for locally stored portraits and scene artwork."""
import pathlib, tempfile, unittest
from unittest import mock
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import artwork, engine

PNG = (b'\x89PNG\r\n\x1a\n'+b'\x00\x00\x00\rIHDR'+b'\x00'*30)

class ArtworkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.db=pathlib.Path(self.temp.name)/'data'/'storyforge.db'
        self.con=engine.open_db(self.db)
        self.world=engine.make_world(self.con,{'title':'Tower','description':'Grey coastal fantasy','sections':[{'title':'Tower','content':'Dark stone','kind':'location'}]})
        self.campaign=engine.new_campaign(self.con,{'world_id':self.world['id'],'pc_name':'Xeminas','appearance':'Platinum hair, purple eyes'})
    def tearDown(self):
        self.con.close();self.temp.cleanup()
    def test_invalid_image_is_not_saved(self):
        for blob in (b'<svg onload=alert(1)>',b'not a picture',b'\x00'*(8*1024*1024+1)):
            with self.subTest(length=len(blob)),self.assertRaises(ValueError):
                artwork.save_portrait(self.db,self.campaign['id'],blob)
        self.assertIsNone(artwork.character_file(self.db,self.campaign['id']))
    def test_portrait_storage_within_data(self):
        target=artwork.save_portrait(self.db,self.campaign['id'],PNG)
        self.assertTrue(target.is_relative_to(self.db.parent))
        self.assertEqual(target.read_bytes(),PNG)
        self.assertEqual(target,artwork.character_file(self.db,self.campaign['id']))
    def test_scene_cache_lock_and_status(self):
        w=self.world['id'];loc='The Ash Quay'
        before=artwork.scene_record(self.con,w,loc,self.db)
        self.assertIsNone(before['url'])
        with self.assertRaisesRegex(ValueError,'Generate'):
            artwork.lock_scene(self.con,w,loc,True,self.db)
        folder=artwork.asset_dir(self.db)/'scenes';folder.mkdir(parents=True)
        name=before['key']+'.png';(folder/name).write_bytes(PNG)
        self.con.execute('INSERT INTO scene_art(world_id,scene_key,location,filename) VALUES(?,?,?,?)',(w,before['key'],loc,name));self.con.commit()
        later=artwork.scene_record(self.con,w,loc,self.db)
        self.assertTrue(later['url'].endswith('/'+before['key']))
        self.assertEqual(artwork.scene_file(self.con,w,before['key'],self.db).read_bytes(),PNG)
        locked=artwork.lock_scene(self.con,w,loc,True,self.db)
        self.assertTrue(locked['locked'])
    def test_no_untrusted_remote_generation(self):
        with mock.patch.dict('os.environ',{'STORYFORGE_COMFY_PORT':'bad'}):
            with self.assertRaises(ValueError):artwork.comfy_base()
        with mock.patch.object(artwork,'comfy_checkpoints',return_value=['local.safetensors']):
            campaign=engine.get_campaign(self.con,self.campaign['id'])
            with self.assertRaisesRegex(ValueError,'Choose'):
                artwork.start_job(self.db,'scene',campaign,self.world,'malicious.ckpt')
    def test_saved_images_not_cleared_when_editing_character(self):
        artwork.save_portrait(self.db,self.campaign['id'],PNG)
        campaign=engine.update_character(self.con,self.campaign['id'],{'pc_name':'Xeminas II'})
        self.assertEqual(campaign['pc_name'],'Xeminas II')
        self.assertTrue(artwork.character_file(self.db,self.campaign['id']).exists())

if __name__=='__main__':unittest.main()

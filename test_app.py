import concurrent.futures, json, os, tempfile, threading, unittest, urllib.request, urllib.error
import base64, io
from PIL import Image
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
import app

class LabTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.previous=app.DB; app.DB=Path(self.tmp.name)/'test.sqlite3'
        mysql_test=os.environ.get('MYSQL_TEST')=='1'
        if mysql_test and not os.environ.get('DB_NAME','').endswith('_qa'): raise RuntimeError('MySQL destructive tests require a dedicated *_qa database')
        self.env=patch.dict(os.environ,{'AI_MODE':'demo','DB_BACKEND':'mysql' if mysql_test else 'sqlite'});self.env.start()
        if os.environ.get('MYSQL_TEST')=='1':
            with app.connect() as c:
                c.execute('SET FOREIGN_KEY_CHECKS=0')
                for table in ['answer_rewrites','knowledge_media','images','feedback','revisions','queries','prompts','knowledge','lab_lock']:
                    c.execute('DROP TABLE IF EXISTS '+table)
                c.execute('SET FOREIGN_KEY_CHECKS=1')
        app.init()
    def tearDown(self):
        self.env.stop(); app.DB=self.previous; self.tmp.cleanup()
    def ask(self,q='一般維護要提前多久申請？',who='小陳'):
        return app.post_api('/api/ask',{'actor':who,'question':q,'conversation':'test-session'})
    def edit(self,d,**changes):
        return app.post_api('/api/knowledge',{**d,'actor':'小林','reason':'更新規範','query_id':None,**changes})
    def test_seed_idempotent(self):
        app.init(); self.assertEqual(len(app.get_api('/api/state',{})['knowledge']),6)
    def test_retrieval_and_unknown(self):
        q=self.ask(); self.assertEqual(q['sources'][0]['id'],1); self.assertIn('3 個工作天',q['answer'])
        self.assertFalse(self.ask('正式資料庫的管理員密碼是什麼？')['sources'])
        self.assertIn('無法確認',self.ask('明天天氣如何？')['answer'])
    def test_update_visible_old_snapshot_immutable(self):
        q=self.ask('測試備份保存幾天？'); d=q['sources'][0]
        self.edit(d,content=d['content'].replace('7 天','14 天'),query_id=q['id'])
        after=self.ask('測試備份保存幾天？','小王')
        self.assertIn('14 天',after['answer']);self.assertEqual(after['sources'][0]['version'],2)
        records=app.get_api('/api/records',{}); old=next(x for x in records['queries'] if x['id']==q['id'])
        self.assertEqual(old['sources'][0]['version'],1);self.assertIn('7 天',old['sources'][0]['content'])
        self.assertEqual(records['revisions'][0]['actor'],'小林');self.assertEqual(records['revisions'][0]['query_id'],q['id'])
    def test_conflict_no_overwrite(self):
        d=app.get_api('/api/state',{})['knowledge'][0];self.edit(d,content='新版')
        with self.assertRaises(app.Problem) as e:self.edit(d,content='過期的編輯')
        self.assertEqual(e.exception.status,409)
    def test_concurrent_edit_only_one_wins(self):
        d=app.get_api('/api/state',{})['knowledge'][0]
        def update(_):
            try:self.edit(d,content='並行新版');return 200
            except app.Problem as e:return e.status
        with concurrent.futures.ThreadPoolExecutor(2) as pool: results=list(pool.map(update,range(2)))
        self.assertEqual(sorted(results),[200,409])
    def test_new_knowledge(self):
        self.edit({'title':'火星測試','tags':'火星','content':'火星測試窗口是小王。'})
        self.assertIn('小王',self.ask('火星測試窗口？')['answer'])
    def test_feedback_dimensions_and_actor(self):
        q=self.ask(); app.post_api('/api/feedback',{'actor':'小王','query_id':q['id'],'correctness':'正確','satisfaction':'太冗長','note':'只需一句'})
        f=app.get_api('/api/records',{})['feedback'][0];self.assertEqual((f['actor'],f['correctness'],f['satisfaction']),('小王','正確','太冗長'))
    def test_counts(self):
        self.ask();self.ask();self.ask('我要安排維護，幾天前要提出？','小林')
        q=app.get_api('/api/records',{})['queries'];self.assertEqual(q[1]['exact_count'],2);self.assertEqual(q[0]['topic_count'],3)
    def test_prompt_trace_and_conflict(self):
        self.ask(); app.post_api('/api/prompt',{'actor':'小林','content':'簡潔回答','reason':'測試','version':1})
        self.assertEqual(self.ask()['prompt_id'],2)
        self.assertEqual(app.get_api('/api/records',{})['queries'][-1]['prompt_id'],1)
        with self.assertRaises(app.Problem):app.post_api('/api/prompt',{'actor':'小林','content':'過期修改','reason':'測試','version':1})
    def test_validation(self):
        for b in [{'actor':'小陳','question':'','conversation':'x'},{'actor':'假名','question':'維護','conversation':'x'}]:
            with self.assertRaises(app.Problem): app.post_api('/api/ask',b)
        with self.assertRaises(app.Problem):self.edit({'id':1,'version':1,'title':'x','tags':'x','content':'x'},query_id=999)
    def test_model_success_and_failure(self):
        captured={}
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return json.dumps({'choices':[{'message':{'content':'提前 3 個工作天。[K1 v1]'}}]}).encode()
        def fake(req,**kw):captured.update(json.loads(req.data));return Response()
        with patch.dict(os.environ,{'AI_MODE':'openai','AI_MODEL':'test-model'}),patch('urllib.request.urlopen',fake):
            q=self.ask();self.assertEqual(q['mode'],'openai');self.assertEqual(captured['messages'][0]['content'],app.DEFAULT_PROMPT)
            self.assertEqual(json.loads(captured['messages'][1]['content'])['reference_data'][0]['version'],1)
        before=len(app.get_api('/api/records',{})['queries'])
        with patch.dict(os.environ,{'AI_MODE':'openai','AI_MODEL':'test-model'}),patch('urllib.request.urlopen',side_effect=OSError):
            with self.assertRaises(app.Problem):self.ask()
        self.assertEqual(before,len(app.get_api('/api/records',{})['queries']))
    def test_http_contract(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_port}'
        try:
            with urllib.request.urlopen(base) as r:self.assertIn('Ditto',r.read().decode());self.assertIn("script-src 'self'",r.headers['Content-Security-Policy'])
            req=urllib.request.Request(base+'/api/ask',json.dumps({'actor':'小陳','question':'維護申請','conversation':'http'}).encode(),{'Content-Type':'application/json'})
            with urllib.request.urlopen(req) as r:self.assertTrue(json.load(r)['sources'])
            d=app.get_api('/api/state',{})['knowledge'][0]
            self.edit(d,new_images=[self.png()])
            image_id=app.get_api('/api/state',{})['knowledge'][0]['images'][0]
            with urllib.request.urlopen(base+'/media/'+image_id) as r:
                self.assertEqual(r.headers['Content-Type'],'image/png');self.assertTrue(r.read().startswith(b'\x89PNG'))
            with urllib.request.urlopen(base+'/app.js') as r:self.assertIn('sourcePreview',r.read().decode())
            req.add_header('Origin','http://evil.example')
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
            self.assertEqual(e.exception.code,403)
            with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+'/app.py')
        finally:server.shutdown();server.server_close();thread.join()
    def test_persistence_on_init(self):
        self.ask(); app.init(); self.assertEqual(len(app.get_api('/api/records',{})['queries']),1)

    def png(self):
        data=io.BytesIO();Image.new('RGB',(2,2),'red').save(data,format='PNG');return base64.b64encode(data.getvalue()).decode()
    def test_media_revision_and_diff(self):
        q=self.ask();d=q['sources'][0]
        self.edit(d,content=d['content'].replace('3 個','4 個'),new_images=[self.png()],query_id=q['id'])
        state=app.get_api('/api/state',{});updated=state['knowledge'][0]
        self.assertEqual(len(updated['images']),1)
        change=next(r for r in state['revisions'] if r['knowledge_id']==d['id'] and r['version']==2)
        self.assertEqual(change['changes'],[{'before':'3','after':'4'}]);self.assertFalse(change['initial'])
        self.assertIn('3 個',change['before_content']);self.assertEqual(change['actor'],'小林')
        self.edit(updated,content=updated['content']+'補充')
        self.assertEqual(app.get_api('/api/state',{})['knowledge'][0]['images'],updated['images'])
        self.assertFalse(q['sources'][0]['images'])
    def test_reject_bad_media_and_foreign_attachment(self):
        d=app.get_api('/api/state',{})['knowledge'][0]
        for image in ['invalid',base64.b64encode(b'<svg></svg>').decode()]:
            with self.assertRaises(app.Problem):self.edit(d,new_images=[image])
        with self.assertRaises(app.Problem):self.edit(d,images=['a'*32],content='不可保存')
        self.assertEqual(app.get_api('/api/state',{})['knowledge'][0]['version'],1)
    def test_concise_requires_model_and_preserves_original(self):
        q=self.ask()
        with self.assertRaises(app.Problem):app.post_api('/api/ask',{'actor':'小王','concise_of':q['id']})
        with patch.dict(os.environ,{'AI_MODE':'openai'}),patch.object(app,'model_answer',return_value='精簡回答') as model:
            out=app.post_api('/api/ask',{'actor':'小王','concise_of':q['id']})
        self.assertEqual(out['sources'],q['sources']);self.assertIn('最多三個要點',model.call_args.args[2])
        records=app.get_api('/api/records',{});self.assertEqual(records['rewrites'][0]['original_id'],q['id'])
        self.assertEqual(records['queries'][-1]['answer'],q['answer'])
    def test_dotenv_keeps_environment_precedence(self):
        from database import load_env
        p=Path(self.tmp.name)/'.env';p.write_text('LAB_ENV_TEST="local value"\nLAB_ENV_OVERRIDE=file\n')
        with patch.dict(os.environ,{'LAB_ENV_OVERRIDE':'environment'}):
            load_env(p);self.assertEqual(os.environ['LAB_ENV_TEST'],'local value');self.assertEqual(os.environ['LAB_ENV_OVERRIDE'],'environment')

if __name__=='__main__':unittest.main(verbosity=2)

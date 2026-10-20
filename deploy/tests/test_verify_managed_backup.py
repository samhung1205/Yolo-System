import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_managed_backup import verify, InvalidBackup


class ManagedCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.name='20261021T000000Z-12345678'
        self.folder=self.root/self.name;self.folder.mkdir()
        with gzip.open(self.folder/'database.sql.gz','wb') as out:out.write(b'SQL fixture')
        data=b'file fixture'
        with tarfile.open(self.folder/'files.tar.gz','w:gz') as out:
            info=tarfile.TarInfo('source/README.md');info.size=len(data);out.addfile(info,io.BytesIO(data))
        with tarfile.open(self.folder/'caddy-data.tar.gz','w:gz'):pass
        self.report={'kind':'sam-yolo-managed-v1','success':True,'restore_verified':True,
            'artifacts':{p.name:self.sha(p.read_bytes()) for p in self.folder.iterdir()},
            'database_sql_sha256':self.sha(b'SQL fixture'),
            'files':{'source/README.md':{'size':len(data),'sha256':self.sha(data)}},'images':{}}
        for kind in ('images','models'):
            (self.root/kind).mkdir()
            path=kind+'/'+('a'*64)+'.tar.gz';(self.root/path).write_bytes(b'cache')
            entry={'path':path,'sha256':self.sha(b'cache')}
            if kind=='images':self.report['images']['sha256:'+'a'*64]=entry
            else:self.report['native_models']=entry
        self.save()

    def sha(self,data):return hashlib.sha256(data).hexdigest()
    def save(self):(self.folder/'manifest.json').write_text(json.dumps(self.report))

    def test_complete_snapshot_and_caches_pass(self):
        self.assertEqual(verify(self.root,self.name)['files'],1)

    def test_missing_model_cache_rejected(self):
        (self.root/self.report['native_models']['path']).unlink()
        with self.assertRaises((InvalidBackup,OSError)):verify(self.root,self.name)

    def test_changed_cache_rejected(self):
        (self.root/self.report['native_models']['path']).write_bytes(b'changed')
        with self.assertRaises(InvalidBackup):verify(self.root,self.name)

    def test_unverified_snapshot_rejected(self):
        self.report['restore_verified']=False;self.save()
        with self.assertRaises(InvalidBackup):verify(self.root,self.name)

    def test_cache_traversal_rejected(self):
        self.report['native_models']['path']='../outside';self.save()
        with self.assertRaises(InvalidBackup):verify(self.root,self.name)

    def test_invalid_snapshot_path_rejected(self):
        with self.assertRaises(InvalidBackup):verify(self.root,'../outside')


if __name__=='__main__':unittest.main()

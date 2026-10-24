import json
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import pytest
from infra_xray.cli import make_server

@pytest.fixture
def server():
    server=make_server({'nodes':[],'safe':True})
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield server
    server.shutdown();server.server_close();thread.join()

def request(server,path='/api/graph',**headers):
    return urlopen(Request('http://127.0.0.1:'+str(server.server_port)+path,headers=headers))

def test_token_required(server):
    with pytest.raises(HTTPError) as e:request(server)
    assert e.value.code==403
    with request(server,Authorization='Bearer '+server.token) as response:
        assert json.load(response)['safe']
        assert response.headers['Cache-Control']=='no-store'
        assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
        assert response.headers.get('Access-Control-Allow-Origin') is None

def test_rebinding_and_cross_site_rejected(server):
    for headers in [{'Host':'evil.example'},{'Sec-Fetch-Site':'cross-site'}]:
        with pytest.raises(HTTPError) as e:request(server,Authorization='Bearer '+server.token,**headers)
        assert e.value.code==403

def test_path_traversal_rejected(server):
    with pytest.raises(HTTPError) as e:request(server,'/../cli.py')
    assert e.value.code==404

from gevent.pywsgi import WSGIServer
import app, sys

port = int( sys.argv[1]) if len( sys.argv) > 1 else 5000
http_server = WSGIServer(('', port), app.app)
http_server.serve_forever()


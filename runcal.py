import sys
import os
import optparse
import json
import ConfigParser
from collections import OrderedDict
from decimal import Decimal, getcontext

import bottle
import healthgraph

from calendar import timegm

from beaker.middleware import SessionMiddleware

__author__ = "Ali Onur Uyar"
__copyright__ = "Copyright 2012, Ali Onur Uyar"
__credits__ = []
__license__ = "GPL"
__version__ = "0.3.0"
__maintainer__ = "Ali Onur Uyar"
__email__ = "aouyar at gmail.com"
__status__ = "Development"


# Defaults
conf = {
    'baseurl': 'http://127.0.0.1:8000',
    'bindaddr': '127.0.0.1',
    'bindport': 8000,
}
ROOT = './app'
defaultConfFilename = 'settings.conf'
bottle.TEMPLATE_PATH = [ROOT]
bottle.BaseTemplate.defaults.update({
    'STATIC_URL': '/static/'
})
getcontext().prec = 3


# Session Options
sessionOpts = {
    'session.type': 'file',
    'session.cookie_expires': 1800,
    'session.data_dir': '/tmp/cache/data',
    'session.lock_dir': '/tmp/cache/data',
    'session.auto': False,
}


class ConfigurationError(Exception):
    """Base classs for Configuration Errors"""
    pass


@bottle.route('<filename:path>')
def server_static(filename):
    return bottle.static_file(filename, root=ROOT)

@bottle.get('/events')
@bottle.post('/events')
def events():
    return { "success": 1, "result": [ { "id": "293", "title": "This is warning class event", "url": "http://www.example.com/", "class": "event-warning", "start": "1362938400000", "end": "1363197686300" }, { "id": "294", "title": "This is information class ", "url": "http://www.example.com/", "class": "event-info", "start": "1363111200000", "end": "1363284086400" }, { "id": "297", "title": "This is success event", "url": "http://www.example.com/", "class": "event-success", "start": "1363284000000", "end": "1363284086400" }, { "id": "54", "title": "This is simple event", "url": "http://www.example.com/", "class": "", "start": "1363629600000", "end": "1363716086400" }, { "id": "532", "title": "This is inverse event", "url": "http://www.example.com/", "class": "event-inverse", "start": "1364407200000", "end": "1364493686400" }, { "id": "548", "title": "This is special event", "url": "http://www.example.com/", "class": "event-special", "start": "1363197600000", "end": "1363629686400" }, { "id": "295", "title": "Event 3", "url": "http://www.example.com/", "class": "event-important", "start": "1364320800000", "end": "1364407286400" } ] }

@bottle.route('/')
def index():
    sess = bottle.request.environ['beaker.session']
    if sess.has_key('rk_access_token'):
        bottle.redirect('/heatmap')
    else:
        rk_auth_mgr = healthgraph.AuthManager(conf['client_id'], conf['client_secret'],
                                          '/'.join((conf['baseurl'], 'login',)))
        rk_auth_uri = rk_auth_mgr.get_login_url()
        rk_button_img = rk_auth_mgr.get_login_button_url('blue', 'black', 300)
        return bottle.template('index.html', {'rk_button_img': rk_button_img,
                                              'rk_auth_uri': rk_auth_uri,})

@bottle.route('/login')
def login():
    sess = bottle.request.environ['beaker.session']
    code = bottle.request.query.get('code')
    if code is not None:
        rk_auth_mgr = healthgraph.AuthManager(conf['client_id'], conf['client_secret'],
                                              '/'.join((conf['baseurl'], 'login',)))
        access_token = rk_auth_mgr.get_access_token(code)
        sess['rk_access_token'] = access_token
        sess.save()
        bottle.redirect('/heatmap')

@bottle.route('/heatmap')
def heatmap():
    sess = bottle.request.environ['beaker.session']
    access_token = sess.get('rk_access_token')
    if access_token is not None:
        user = healthgraph.User(session=healthgraph.Session(access_token))
        profile = user.get_profile()
        records = user.get_records()
        act_iter = user.get_fitness_activity_iter()
        activities = OrderedDict()
        try:
            while True:
                activity = act_iter.next()
                timestamp = timegm(activity['start_time'].timetuple())
                distance = float(Decimal(activity['total_distance']) / 1)
                activities[timestamp] = distance
        except StopIteration:
            pass
        return bottle.template('welcome.html',
                               profile=profile,
                               activities=json.dumps(activities))
    else:
        bottle.redirect('/')

@bottle.route('/api/heatmap')
def api_heatmap():
    sess = bottle.request.environ['beaker.session']
    access_token = sess.get('rk_access_token')
    if access_token is not None:
        user = healthgraph.User(session=healthgraph.Session(access_token))
        records = user.get_records()
        act_iter = user.get_fitness_activity_iter()
        activities = OrderedDict()
        try:
            while True:
                activity = act_iter.next()
                timestamp = timegm(activity['start_time'].timetuple())
                distance = float(Decimal(activity['total_distance']) / 1)
                activities[timestamp] = distance
        except StopIteration:
            pass
        return activities
    else:
        bottle.abort(403, 'Missing access token')

@bottle.route('/logout')
def logout():
    sess = bottle.request.environ['beaker.session']
    sess.delete()
    bottle.redirect('/')

@bottle.route('/view_access_token')
def view_access_token():
    sess = bottle.request.environ['beaker.session']
    access_token = sess.get('rk_access_token')
    if access_token is not None:
        remote_addr = bottle.request.get('REMOTE_ADDR')
        return bottle.template('access_token.html',
                               remote_addr=remote_addr,
                               access_token=(access_token
                                             if remote_addr == '127.0.0.1'
                                             else None))
    else:
        bottle.redirect('/')




def parse_cmdline(argv=None):
    """Parse command line options.

    @param argv: List of command line arguments. If None, get list from system.
    @return:     Tuple of Option List and Argument List.

    """
    parser = optparse.OptionParser()
    parser.add_option('-c', '--conf', help='Configuration file path.',
                      dest='confpath',default=None)
    parser.add_option('-p', '--bindport',
                      help='Bind to TCP Port. (Default: %d)' % conf['bindport'],
                      dest='bindport', type='int', default=None, action='store')
    parser.add_option('-b', '--bindaddr',
                      help='Bind to IP Address. (Default: %s)' % conf['bindaddr'],
                      dest='bindaddr', default=None, action='store')
    parser.add_option('-u', '--baseurl',
                      help='Base URL. (Default: %s)' % conf['baseurl'],
                      dest='baseurl', default=None, action='store')
    parser.add_option('-D', '--devel', help='Enable development mode.',
                      dest='devel', default=False, action='store_true')
    if argv is None:
        return parser.parse_args()
    else:
        return parser.parse_args(argv[1:])


def parse_conf_files(conf_paths):
    """Parse the configuration file and return dictionary of configuration
    options.

    @param conf_paths: List of configuration file paths to parse.
    @return:           Dictionary of configuration options.

    """
    conf_file = ConfigParser.RawConfigParser()
    conf_read = conf_file.read(conf_paths)
    conf = {}
    try:
        if conf_read:
            conf['client_id'] = conf_file.get('runkeeper', 'client_id')
            conf['client_secret'] = conf_file.get('runkeeper', 'client_secret')
            if conf_file.has_option('runkeeper', 'bindport'):
                conf['bindport'] = conf_file.getint('runkeeper', 'bindport')
            if conf_file.has_option('runkeeper', 'bindaddr'):
                conf['bindaddr'] = conf_file.get('runkeeper', 'bindaddr')
            if conf_file.has_option('runkeeper', 'baseurl'):
                conf['baseurl'] = conf_file.get('runkeeper', 'baseurl')
            return conf
    except ConfigParser.Error:
        raise ConfigurationError("Error parsing configuration file(s): %s\n"
                                 % sys.exc_info()[1])
    else:
        raise ConfigurationError("No valid configuration file (%s) found."
                                 % defaultConfFilename)


def main(argv=None):
    """Main Block - Configure and run the Bottle Web Server."""
    cmd_opts = parse_cmdline(argv)[0]
    if cmd_opts.confpath is not None:
        if os.path.exists(cmd_opts.confpath):
            conf_paths = [cmd_opts.confpath,]
        else:
            return "Configuration file not found: %s" % cmd_opts.confpath
    else:
        conf_paths = [os.path.join(path, defaultConfFilename)
                      for path in ('/etc', '.',)]
    try:
        conf.update(parse_conf_files(conf_paths))
    except ConfigurationError:
        return(sys.exc_info()[1])
    if cmd_opts.bindport is not None:
        conf['bindport'] = cmd_opts.bindport
    if cmd_opts.bindaddr is not None:
        conf['bindaddr'] = cmd_opts.bindaddr
    if cmd_opts.baseurl is not None:
        conf['baseurl'] = cmd_opts.baseurl
    if cmd_opts.devel:
        from bottle import debug
        debug(True)
    app = SessionMiddleware(bottle.app(), sessionOpts)
    bottle.run(app=app, host=conf['bindaddr'], port=conf['bindport'],
               reloader=cmd_opts.devel)


if __name__ == "__main__":
    sys.exit(main())

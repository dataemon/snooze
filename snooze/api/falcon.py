#!/usr/bin/python
import os
import json

from pathlib import Path

import falcon
from falcon_auth import FalconAuthMiddleware, BasicAuthBackend, JWTAuthBackend
import requests
from wsgiref import simple_server
from bson.json_util import loads, dumps

from snooze.api.base import Api, BasicRoute
from snooze.utils import config, write_config

from logging import getLogger
log = getLogger('snooze.api')

from hashlib import sha256
from base64 import b64decode, b64encode

from multiprocessing import Process
from .socket import SocketServer

from ldap3 import Server, Connection, ALL, SUBTREE
from ldap3.core.exceptions import LDAPOperationResult, LDAPExceptionError

def authorize(func):
    def _f(self, req, resp, *args, **kw):
        user_payload = req.context['user']['user']
        if (self.plugin and hasattr(self.plugin, 'name')):
            plugin_name = self.plugin.name
        elif self.name:
            plugin_name = self.name
        if plugin_name:
            read_permissions = ['ro_all', 'rw_all', 'ro_'+plugin_name, 'rw_'+plugin_name]
            write_permissions = ['rw_all', 'rw_'+plugin_name]
        else:
            plugin_name = 'unknown'
            read_permissions = ['ro_all', 'rw_all']
            write_permissions = ['rw_all']
        endpoint = func.__name__
        log.debug("Checking user {} authorization '{}' for plugin {}".format(user_payload, endpoint, plugin_name))
        method = user_payload['method']
        name = user_payload['name']
        if name == 'root' and method == 'root':
            log.warning("Root user detected! Authorized but please use a proper admin role if possible")
            return func(self, req, resp, *args, **kw)
        else:
            capabilities = user_payload.get('capabilities', [])
            capabilities.append('any')
            if endpoint == 'on_get':
                if self.authorization_policy and any(cap in capabilities for cap in self.authorization_policy.get('read', [])):
                    log.debug("User {} has any read capabilities {}. Authorized".format(name, self.authorization_policy.get('read')))
                    return func(self, req, resp, *args, **kw)
                elif any(cap in capabilities for cap in read_permissions):
                    return func(self, req, resp, *args, **kw)
            elif endpoint == 'on_post' or endpoint == 'on_put' or endpoint == 'on_delete':
                if self.check_permissions:
                    log.debug("Will double check {} permissions".format(name))
                    capabilities = self.get_capabilities(self.get_roles(name, method))
                if len(capabilities) > 0:
                    if self.authorization_policy and any(cap in capabilities for cap in self.authorization_policy.get('write', [])):
                        log.debug("User {} has any write capabilities {}. Authorized".format(name, self.authorization_policy.get('write')))
                        return func(self, req, resp, *args, **kw)
                    elif any(cap in capabilities for cap in write_permissions):
                        return func(self, req, resp, *args, **kw)
        raise falcon.HTTPForbidden('Forbidden', 'Permission Denied')
    return _f

class FalconRoute(BasicRoute):
    def inject_payload_media(self, req, resp):
        user_payload = req.context['user']['user']
        log.debug("Injecting payload {} to {}".format(user_payload, req.media))
        if isinstance(req.media, list):
            for media in req.media:
                media['name'] = user_payload['name']
                media['method'] = user_payload['method']
        else:
            req.media['name'] = user_payload['name']
            req.media['method'] = user_payload['method']

    def inject_payload_search(self, req, s):
        user_payload = req.context['user']['user']
        to_inject = ['AND', ['=', 'name', user_payload['name']], ['=', 'method', user_payload['method']]]
        if s:
            return ['AND', s, to_inject]
        else:
            return to_inject

    def update_password(self, media):
        password = media.pop('password', None)
        name = media.get('name')
        method = media.get('method')
        if not password or not name or method != 'local':
            log.debug("Skipping updating password")
            return
        log.debug("Updating password for {} user {}".format(method, name))
        user_password = {}
        user_password['name'] = name
        user_password['method'] = method
        user_password['password'] = sha256(password.encode('utf-8')).hexdigest()
        self.core.db.write('user.password', user_password, 'name,method')

class CapabilitiesRoute(BasicRoute):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'role'

    @authorize
    def on_get(self, req, resp):
        log.debug("Listing capabilities")
        try:
            capabilities = ['rw_all', 'ro_all']
            for plugin in self.api.core.plugins:
                capabilities.append('rw_' + plugin.name)
                capabilities.append('ro_' + plugin.name)
                for additional_capability in plugin.capabilities:
                    capabilities.append(additional_capability)
            log.debug("List of capabilities: {}".format(capabilities))
            resp.content_type = falcon.MEDIA_JSON
            resp.status = falcon.HTTP_200
            resp.media = {
                'data': capabilities,
            }
        except Exception as e:
            log.exception(e)
            resp.status = falcon.HTTP_503

class ActionPluginRoute(BasicRoute):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'action'

    @authorize
    def on_get(self, req, resp, action=None):
        log.debug("Listing actions")
        plugin_name = req.params.get('action') or action
        try:
            plugins = []
            loaded_plugins = self.api.core.action_plugins
            if plugin_name:
                loaded_plugins = [self.api.core.get_action_plugin(plugin_name)]
            for plugin in loaded_plugins:
                log.debug("Retrieving action {} metadata".format(plugin.name))
                plugins.append(plugin.get_metadata())
            log.debug("List of actions: {}".format(plugins))
            resp.content_type = falcon.MEDIA_JSON
            resp.status = falcon.HTTP_200
            resp.media = {
                'data': plugins,
            }
        except Exception as e:
            log.exception(e)
            resp.status = falcon.HTTP_503

class AlertRoute(BasicRoute):
    auth = {
        'auth_disabled': True
    }

    def on_post(self, req, resp):
        log.debug("Received log {}".format(req.media))
        try:
            self.core.process_record(req.media)
            resp.status = falcon.HTTP_200
        except Exception as e:
            log.exception(e)
            resp.status = falcon.HTTP_503

class LoginRoute(BasicRoute):
    auth = {
        'auth_disabled': True
    }

    def on_get(self, req, resp):
        log.debug("Listing authentication backends")
        try:
            backends = [{'name':self.api.auth_routes[backend].name, 'endpoint': backend} for backend in self.api.auth_routes.keys() if self.api.auth_routes[backend].enabled]
            resp.content_type = falcon.MEDIA_JSON
            resp.status = falcon.HTTP_200
            resp.media = {
                'data': {'backends': backends, 'default': self.api.core.general_conf.get('default_auth_backend') or ''},
            }
        except Exception as e:
            log.exception(e)
            resp.status = falcon.HTTP_503

class ReloadRoute(BasicRoute):
    auth = {
        'auth_disabled': True
    }

    def on_post(self, req, resp):
        media = req.media.copy()
        if media.get('reload_token', '-') == self.api.core.secrets.get('reload_token', '+'):
            log.debug("Reloading conf ({}, {}), backend {}, sync {}".format(media.get('filename', ''), media.get('conf', ''), media.get('reload', ''), media.get('sync', False)))
            results = self.api.write_and_reload(media.get('filename'), media.get('conf'), media.get('reload'), media.get('sync', False))
            resp.content_type = falcon.MEDIA_TEXT
            resp.status = results.get('status', falcon.HTTP_503)
            resp.text = results.get('text', '')
        else:
            resp.status = falcon.HTTP_401
            resp.text = 'Invalid secret reload token'

class ClusterRoute(BasicRoute):
    auth = {
        'auth_disabled': True
    }

    def on_get(self, req, resp):
        log.debug("Listing cluster members")
        if self.api.core.cluster.enabled:
            if req.params.get('self', False):
                members = self.api.core.cluster.get_self()
            else:
                members = self.api.core.cluster.get_members()
            resp.content_type = falcon.MEDIA_JSON
            resp.status = falcon.HTTP_200
            resp.media = {
                'data': members,
            }
        else:
            resp.text = 'Clustering had been disabled'
            resp.status = falcon.HTTP_503

class CORS(object):
    def __init__(self):
        pass

    def process_response(self, req, resp, resource, req_succeeded):
        resp.set_header('Access-Control-Allow-Origin', '*')
        if (
            req_succeeded
            and req.method == 'OPTIONS'
            and req.get_header('Access-Control-Request-Method')
        ):
            allow = resp.get_header('Allow')
            resp.delete_header('Allow')

            allow_headers = req.get_header('Access-Control-Request-Headers', default='*')
            resp.set_headers(
                (
                    ('Access-Control-Allow-Methods', allow),
                    ('Access-Control-Allow-Headers', allow_headers),
                    ('Access-Control-Max-Age', '86400'),  # 24 hours
                )
            )

class AuthRoute(BasicRoute):
    auth = {
        'auth_disabled': True
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_header_prefix = 'Basic'
        self.userplugin = self.api.core.get_core_plugin('user')
        self.enabled = True

    def parse_auth_token_from_request(self, auth_header):
        """
        Parses and returns Auth token from the request header. Raises
        `falcon.HTTPUnauthoried exception` with proper error message
        """
        if not auth_header:
            raise falcon.HTTPUnauthorized(
                description='Missing Authorization Header')

        parts = auth_header.split()

        if parts[0].lower() != self.auth_header_prefix.lower():
            raise falcon.HTTPUnauthorized(
                description='Invalid Authorization Header: '
                            'Must start with {0}'.format(self.auth_header_prefix))

        elif len(parts) == 1:
            raise falcon.HTTPUnauthorized(
                description='Invalid Authorization Header: Token Missing')
        elif len(parts) > 2:
            raise falcon.HTTPUnauthorized(
                description='Invalid Authorization Header: Contains extra content')

        return parts[1]

    def _extract_credentials(self, req):
        auth = req.get_header('Authorization')
        token = self.parse_auth_token_from_request(auth_header=auth)
        try:
            token = b64decode(token).decode('utf-8')

        except Exception:
            raise falcon.HTTPUnauthorized(
                description='Invalid Authorization Header: Unable to decode credentials')

        try:
            username, password = token.split(':', 1)
        except ValueError:
            raise falcon.HTTPUnauthorized(
                description='Invalid Authorization: Unable to decode credentials')

        return username, password

    def parse_user(self, user):
        return user

    def inject_permissions(self, user):
        roles = self.get_roles(user['name'], user['method'])
        capabilities = self.get_capabilities(roles)
        user['roles'] = roles
        user['capabilities'] = capabilities

    def on_post(self, req, resp):
        if self.enabled:
            self.authenticate(req, resp)
            user = self.parse_user(req.context['user'])
            if self.userplugin:
                self.userplugin.manage_db(user)
            self.inject_permissions(user)
            log.debug("Context user: {}".format(user))
            token = self.api.jwt_auth.get_auth_token(user)
            log.debug("Generated token: {}".format(token))
            resp.content_type = falcon.MEDIA_JSON
            resp.status = falcon.HTTP_200
            resp.media = {
                'token': token,
            }
        else:
            resp.content_type = falcon.MEDIA_JSON
            resp.status = falcon.HTTP_409
            resp.media = {
                'response': 'Backend disabled',
            }

    def authenticate(self, req, resp):
        pass

    def reload(self):
        pass

class LocalAuthRoute(AuthRoute):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'Local'
        self.reload()

    def reload(self):
        conf = config('general')
        self.enabled = conf.get('local_users_enabled') or False
        log.debug("Authentication backend 'local' status: {}".format(self.enabled))

    def authenticate(self, req, resp):
        username, password = self._extract_credentials(req)
        password_hash = sha256(password.encode('utf-8')).hexdigest()
        log.debug("Attempting login for {}, with password hash {}".format(username, password_hash))
        user_search = self.core.db.search('user', ['AND', ['=', 'name', username], ['=', 'method', 'local']])
        try:
            if user_search['count'] > 0:
                db_password_search = self.core.db.search('user.password', ['AND', ['=', 'name', username], ['=', 'method', 'local']])
                try:
                    db_password = db_password_search['data'][0]['password']
                except:
                    raise falcon.HTTPUnauthorized(
                		description='Password not found')
                if db_password == password_hash:
                    log.debug('Password was correct for user %s', username)
                    req.context['user'] = username
                else:
                    log.debug('Password was incorrect for user %s', username)
                    raise falcon.HTTPUnauthorized(
                		description='Invalid Username/Password')
            else:
                log.debug('User %s does not exist', username)
                raise falcon.HTTPUnauthorized(
                	description='User does not exist')
        except Exception as e:
            log.exception('Exception while trying to compare passwords')
            raise falcon.HTTPUnauthorized(
           		description='Exception while trying to compare passwords')

    def parse_user(self, user):
        return {'name': user, 'method': 'local'}

class LdapAuthRoute(AuthRoute):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'Ldap'
        self.reload()

    def reload(self):
        conf = config('ldap_auth')
        self.enabled = conf.get('enabled') or False
        if self.enabled:
            try:
                self.base_dn = conf['base_dn']
                self.user_filter = conf['user_filter']
                self.email_attribute = conf.get('email_attribute') or 'mail'
                self.display_name_attribute = conf.get('display_name_attribute') or 'cn'
                self.member_attribute = conf.get('member_attribute') or 'memberof'
                self.auth_header_prefix = conf.get('auth_header_prefix') or 'Basic'
                self.bind_dn = conf['bind_dn']
                self.bind_password = conf['bind_password']
                self.port = conf.get('port') or ''
                if self.port:
                    self.server = Server(conf['host'], port=self.port, get_info=ALL)
                else:
                    self.server = Server(conf['host'], get_info=ALL)
                bind_con = Connection(
                    self.server,
                    user=self.bind_dn,
                    password=self.bind_password,
                    raise_exceptions=True
                )
                if not bind_con.bind():
                    log.error(f"Cannot BIND to LDAP server: {conf['host']}{conf['port']}")
                    self.enabled = False
            except Exception as err:
                log.exception(err)
                self.enabled = False
                pass
        log.debug("Authentication backend 'ldap' status: {}".format(self.enabled))

    def _search_user(self, username):
        try:
            bind_con = Connection(
                self.server,
                user=self.bind_dn,
                password=self.bind_password,
                raise_exceptions=True
            )
            bind_con.bind()
            user_filter = self.user_filter.replace('%s', username)
            bind_con.search(
                search_base = self.base_dn,
                search_filter = user_filter,
                attributes = [self.display_name_attribute, self.email_attribute, self.member_attribute],
                search_scope = SUBTREE
            )
            response = bind_con.response
            if (
                bind_con.result['result'] == 0
                and len(response) > 0
                and 'dn' in response[0].keys()
            ):
                user_dn = response[0]['dn']
                attributes = response[0]['attributes']
                return {'name': username, 'dn': user_dn, 'groups': attributes[self.member_attribute]}
            else:
                # Could not find user in search
                raise falcon.HTTPUnauthorized(description=f"Error in search: Could not find user {username} in LDAP search")
        except LDAPOperationResult as err:
            raise falcon.HTTPUnauthorized(description=f"Error during search: {err}")
        except LDAPExceptionError as err:
            raise falcon.HTTPUnauthorized(description=f"Error during search: {err}")

    def _bind_user(self, user_dn, password):
        try:
            user_con = Connection(
                self.server,
                user=user_dn,
                password=password,
                raise_exceptions=True
            )
            user_con.bind()
            return user_con
        except LDAPOperationResult as err:
            raise falcon.HTTPUnauthorized(description=f"Error during bind: {err}")
        except LDAPExceptionError as err:
            raise falcon.HTTPUnauthorized(description=f"Error during bind: {err}")
        finally:
            user_con.unbind()

    def authenticate(self, req, resp):
        username, password = self._extract_credentials(req)
        user = self._search_user(username)
        user_con = self._bind_user(user['dn'], password)
        if user_con.result['result'] == 0:
            req.context['user'] = user
        else:
            raise falcon.HTTPUnauthorized(description="")

    def parse_user(self, user):
        return {'name': user['name'], 'groups': list(map(lambda x: x.split(',')[0].split('=')[1], user['groups'])), 'method': 'ldap'}

SNOOZE_GLOBAL_RUNDIR = '/var/run/snooze'
SNOOZE_LOCAL_RUNDIR = "/var/run/user/{}".format(os.getuid())

class BackendApi():
    def init_api(self, core):
        # Authentication
        self.core = core

        # JWT setup
        self.secret = self.core.secrets['jwt_secret_key']
        def auth(payload):
            log.debug("Payload received: {}".format(payload))
            return payload
        self.jwt_auth = JWTAuthBackend(auth, self.secret)

        # Socket
        log.debug('BackendAPI: init_api')
        socket_path = self.core.conf.get('socket_path', None)
        log.debug("Socket path: {}".format(socket_path))
        self.socket_server = SocketServer(self.jwt_auth, socket_path=socket_path)
        self.socket = Process(target=self.socket_server.serve)

        # Handler
        self.handler = falcon.API(middleware=[CORS(), FalconAuthMiddleware(self.jwt_auth)])
        self.handler.req_options.auto_parse_qs_csv = False
        self.auth_routes = {}
        # Alerta route
        self.add_route('/alert', AlertRoute(self))
        # List route
        self.add_route('/login', LoginRoute(self))
        # Reload route
        self.add_route('/reload', ReloadRoute(self))
        # Cluster route
        self.add_route('/cluster', ClusterRoute(self))
        # Capabilities route
        self.add_route('/capabilities', CapabilitiesRoute(self))
        # Capabilities route
        self.add_route('/plugin/action', ActionPluginRoute(self))
        self.add_route('/plugin/action/{action}', ActionPluginRoute(self))
        # Basic auth setup
        self.auth_routes['local'] = LocalAuthRoute(self)
        self.add_route('/login/local', self.auth_routes['local'])
        # Ldap auth
        self.auth_routes['ldap'] = LdapAuthRoute(self)
        self.add_route('/login/ldap', self.auth_routes['ldap'])

    def add_route(self, route, action):
        self.handler.add_route(route, action)

    def serve(self):
        log.debug('Starting socket API')
        self.socket.start()
        log.debug('Starting REST API')
        httpd = simple_server.make_server('0.0.0.0', 9001, self.handler)
        ssl = self.core.conf.get('ssl')
        if ssl == True:
            certfile = self.core.conf.get('certfile')
            keyfile = self.core.conf.get('keyfile')
            httpd.socket = ssl.wrap_socket(
                httpd.socket, server_side=True,
                certfile=certfile,
                keyfile=keyfile
            )
        httpd.serve_forever()
        #self.socket.join()

    def get_root_token(self):
        return self.jwt_auth.get_auth_token({'name': 'root', 'method': 'root', 'capabilities': ['rw_all']})

    def reload(self, filename, auth_backends):
        reloaded_auth = []
        reloaded_conf = []
        try:
            if self.core.reload_conf(filename):
                reloaded_conf.append(filename)
            for auth_backend in auth_backends:
                if self.auth_routes.get(auth_backend):
                    log.debug("Reloading {} auth backend".format(auth_backend))
                    self.auth_routes[auth_backend].reload()
                    reloaded_auth.append(auth_backend)
                else:
                    log.debug("Authentication backend '{}' not found".format(auth_backend))
            if len(reloaded_auth) > 0 or len(reloaded_conf) > 0:
                return {'status': falcon.HTTP_200, 'text': "Reloaded auth '{}' and conf {}".format(reloaded_auth, reloaded_conf)}
            else:
                return {'status': falcon.HTTP_404, 'text': 'Error while reloading'}
        except Exception as e:
            log.exception(e)
            return {'status': falcon.HTTP_503}
            
    def write_and_reload(self, filename, conf, reload_conf, sync = False):
        result_dict = {}
        log.debug("Will write to {} config {} and reload {}".format(filename, conf, reload_conf))
        if filename and conf:
            res = write_config(filename, conf)
            if 'error' in res.keys():
                return {'status': falcon.HTTP_503, 'text': res['error']}
            else:
                result_dict = {'status': falcon.HTTP_200, 'text': "Reloaded config file {}".format(res['file'])}
        if reload_conf:
            auth_backends = reload_conf.get('auth_backends', [])
            if auth_backends:
                result_dict = self.reload(filename, auth_backends)
            plugins = reload_conf.get('plugins', [])
            if plugins:
                result_dict = self.reload_plugins(plugins)
        if sync and self.cluster:
            self.cluster.write_and_reload(filename, conf, reload_conf)
        return result_dict

    def reload_plugins(self, plugins):
        plugins_error = []
        plugins_success = []
        log.debug("Reloading plugins {}".format(plugins))
        for plugin_name in plugins:
            plugin = self.core.get_core_plugin(plugin_name)
            if plugin:
                plugin.reload_data()
                plugins_success.append(plugin)
            else:
                plugins_error.append(plugin)
        if plugins_error:
            return {'status': falcon.HTTP_404, 'text': "The following plugins could not be found: {}".format(plugins_error)}
        else:
            return {'status': falcon.HTTP_200, 'text': "Reloaded plugins: {}".format(plugins_success)}


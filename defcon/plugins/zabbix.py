"""DefCon Zabbix plugin."""
from django.conf import settings
from defcon.plugins import base
import datetime
from pyzabbix.api import ZabbixAPI
import jinja2

DEFAULT_API = getattr(settings, 'ZABBIX_API', None)


class Zabbix(base.Plugin):
    """DefCon Static plugin.

    Config:
    ```python
    {
      'api': 'https://zabbix', // Url to root API.
      'username': 'user', // zabbix api username
      'password': 'pass1', // zabbix password
      'proxy': 'zab-proxy-001', // Hosts monitored by this proxy
      'defcon': int, // override on trigger. add tags, defcon: int
      'hostgroups': [ 'group1' ], // array of group names (str)
      'severity': 'high' // minimum trigger level ( info - disaster )
    }
    ```
    """

    def __init__(self, config=None):
        """Create an instance of the plugin."""
        super(Zabbix, self).__init__(config)

        if config is None:
            config = {}

        self.api_url = config.get('api', DEFAULT_API)
        self.defcon = config.get('defcon', 1)
        self.level = config.get('severity', None)

        username = config.get('username', None)
        password = config.get('password', None)
        hostgroups = config.get('hostgroups', None)

        if not config:
            return

        self.zapi = ZabbixAPI(
            url=self.api_url,
            user=username,
            password=password
        )
        self.f = {}
        self.time = datetime.datetime.now().isoformat()
        self.proxy = config.get('proxy', None)
        if self.proxy:
            for proxy in self.zapi.proxy.get(monitored_hosts=1,
                                             output='extend'):
                if proxy['host'] == self.proxy:
                    self.proxyid = proxy['proxyid']
                    self.f['proxy_hostid'] = self.proxyid
        if hostgroups:
            self.groups = []
            g = {a['name']: a['groupid'] for a in self.zapi.hostgroup.get(
                        output=['name', 'groupid'])}
            try:
                for group in hostgroups:
                    self.groups.append(g[group])
            except KeyError:
                pass

    @staticmethod
    def render(template, data):
        """Render a string as a template."""
        env = jinja2.Environment()
        return env.from_string(template).render(**data)

    @property
    def severity(self) -> int:
        severity = {
            'default': 0,
            'info': 1,
            'warning': 2,
            'average': 3,
            'high': 4,
            'disaster': 5,
        }
        try:
            return severity[self.level]
        except KeyError:
            return 0

    @property
    def short_name(self):
        """Return the short name."""
        return 'zabbix'

    @property
    def name(self):
        """Return the name."""
        return 'Zabbix'

    @property
    def description(self):
        """Return the description."""
        return 'Returns statuses based on triggers on zabbix.'

    @property
    def link(self):
        """Return the link."""
        return 'https://github.com/iksaif/defcon'

    def statuses(self):
        """Return the generated statuses."""
        ret = {}

        if self._config is None:
            return ret
        if len(self.groups) > 0:
            h = self.zapi.host.get(groupids=self.groups,
                                   filter=self.f, output=['hostid', 'name'])
        else:
            h = self.zapi.host.get(filter=self.f, output=['hostid', 'name'])
        host_list = [p['hostid'] for p in h]
        host_dict = {a['hostid']: a['name'] for a in h}

        triggers = self.zapi.trigger.get(only_true=1,
                                         skipDependent=1,
                                         monitored=1,
                                         active=1,
                                         output='extend',
                                         expandDescription=1,
                                         filter={'hostid': host_list},
                                         selectHosts=host_list,
                                         selectTags='extend',
                                         )

        unack_triggers = self.zapi.trigger.get(only_true=1,
                                               skipDependent=1,
                                               monitored=1,
                                               active=1,
                                               output=['description',
                                                       'name',
                                                       'hosts'],
                                               expandDescription=1,
                                               filter={'hostid': host_list},
                                               selectHosts=host_list,
                                               withLastEventUnacknowledged=1,
                                               )
        unack_trigger_ids = [t['triggerid'] for t in unack_triggers]
        for t in triggers:
            t['unacknowledged'] = True if t['triggerid'] in unack_trigger_ids \
                else False
        for t in triggers:
            status = None
            if int(t['value']) != 1:
                continue
            if not t['unacknowledged']:
                continue
            if int(t['priority']) >= self.severity:
                # Try to
                try:
                    self.defcon = int({i['tag']: i['value'] \
                                       for i in t['tags']}['defcon'])
                except KeyError:
                    pass
                status = base.Status(
                    'zabbix alert, host: {}'.format(
                        host_dict[t['hosts'][0]['hostid']]),
                    self.defcon,
                    '{}/hostinventories.php?hostid={}&triggerid={}'.format(
                        self.api_url,
                        t['hosts'][0]['hostid'],
                        t['triggerid']),
                    description='desc: {}'.format(t['description']),
                    time_start=self.time,
                )
                if status is not None:
                    ret[status['id']] = status

        return ret
